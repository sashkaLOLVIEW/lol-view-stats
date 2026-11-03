#!/usr/bin/env python3
"""Download each player's final items (and runes) for every finished game of the event from Riot's lolesports live-stats feed.

    python fetch_items.py            -> data/items_cache.json   (one entry per Riot game id; finished games never change, so they are fetched once)

The feed is unofficial. Any failure leaves the cache as it is and exits 0, so the site simply builds without (new) items.
"""
import json, os, sys, time, datetime as dt
from pathlib import Path
import requests

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "data" / "items_cache.json"
DONE = ROOT / "data" / "items_done.json"      # match ids whose games are all cached: not asked about again
KEY = os.environ.get("LOLESPORTS_API_KEY", "").strip() or "0TvQnueqKa5mxJntVWt0w4LpLfEkrV1Ta8rQBb9Z"
GW = "https://esports-api.lolesports.com/persisted/gw"
FEED = "https://feed.lolesports.com/livestats/v1"
H = {"x-api-key": KEY, "User-Agent": "lol-view-stats fan site"}
# lolesports slugs of the events the site covers (matched against each league's slug, case-insensitive). Worlds is the event on the home page;
# the others only feed the post game pages of the filtered scopes. Order = priority when the time budget runs out (international events first).
LEAGUES = [("worlds", "2026-10-22"), ("msi", "2026-01-01"), ("first_stand", "2026-01-01"), ("esports_world_cup", "2026-01-01"), ("ewc", "2026-01-01"),
           ("lck", "2026-01-01"), ("lpl", "2026-01-01"), ("lec", "2026-01-01"), ("lcs", "2026-01-01"), ("lcp", "2026-01-01"), ("cblol-brazil", "2026-01-01"), ("cblol", "2026-01-01")]
LEAGUE_SLUG = "worlds"
SINCE = "2026-10-22"              # Worlds: ignore matches before this date (used by fetch_riot_games.py)
MAX_PAGES = 30
TRINKET_IDS = {3330, 3340, 3363, 3364}
BUDGET = 480                      # seconds of feed requests per run
FORMAT = 5                        # bump to refetch every older cache entry (v2 could carry a trinket copied from an earlier frame)
ROLES = {"top": "top", "jungle": "jng", "mid": "mid", "bottom": "bot", "support": "sup"}   # Riot role -> Oracle's Elixir position

def get(url, **params):
    for attempt in range(3):
        r = requests.get(url, params=params, headers=H, timeout=40)
        if r.status_code == 429: time.sleep(5 * (attempt + 1)); continue
        r.raise_for_status(); return r.json()
    raise RuntimeError("rate limited: " + url)

def team_state(f):
    """Objective counters of one /window frame: [[towers, inhibitors, barons, [dragon types...]] blue, red]."""
    out = []
    for side in ("blueTeam", "redTeam"):
        t = f.get(side) or {}
        out.append([int(t.get("towers") or 0), int(t.get("inhibitors") or 0), int(t.get("barons") or 0), [str(d).lower() for d in (t.get("dragons") or [])]])
    return out

def obj_events(states):
    """[[minute, side 0/1, kind]] from consecutive (minute, team_state) samples; an event is placed in the middle of the interval it was seen in.
    kind: turret, inhibitor, nashor (baron) or the dragon type (ocean, infernal, cloud, mountain, hextech, chemtech, elder)."""
    ev, prev = [], None
    for m, st in states:
        if prev is not None:
            pm, ps = prev
            for sd in (0, 1):
                a, b = ps[sd], st[sd]; mid = round((pm + m) / 2, 2)
                for _ in range(max(0, b[0] - a[0])): ev.append([mid, sd, "turret"])
                for _ in range(max(0, b[1] - a[1])): ev.append([mid, sd, "inhibitor"])
                for _ in range(max(0, b[2] - a[2])): ev.append([mid, sd, "nashor"])
                for d in b[3][len(a[3]):]: ev.append([mid, sd, d])
        prev = (m, st)
    return ev

def iso(s): return dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
def fmt(t): return t.strftime("%Y-%m-%dT%H:%M:%S.000Z")
def late(t0):
    """A moment after the game ended, for asking the feed for its final frames. Riot answers 400 for a time in the future, so a game that
    finished less than 3 hours ago is asked at 'now' (minus a minute) instead."""
    return floor10(min(t0 + dt.timedelta(hours=3), dt.datetime.now(dt.timezone.utc) - dt.timedelta(seconds=60)))
def floor10(t): return t.replace(second=t.second - t.second % 10, microsecond=0)

def finished_matches(lid, since):
    out, token = {}, None
    for _ in range(MAX_PAGES):
        p = dict(hl="en-US", leagueId=lid)
        if token: p["pageToken"] = token
        sch = get(GW + "/getSchedule", **p)["data"]["schedule"]
        evs = sch.get("events") or []
        for e in evs:
            if e.get("state") == "completed" and e.get("match") and (e.get("startTime") or "")[:10] >= since:
                out[e["match"]["id"]] = e
        old = [e for e in evs if e.get("startTime")]
        token = (sch.get("pages") or {}).get("older")
        if not token or (old and min(e["startTime"] for e in old)[:10] < since): break
    return out

def fetch_game(game, number, codes, bo=0):
    gid = game["id"]
    w0 = get(FEED + "/window/" + gid)
    md = w0["gameMetadata"]; t0 = iso(w0["frames"][0]["rfc460Timestamp"])
    wend = get(FEED + "/window/" + gid, startingTime=fmt(late(t0)))
    fr = wend.get("frames") or []
    if not fr or fr[-1].get("gameState") != "finished": raise RuntimeError("no finished frame")
    tend = iso(fr[-1]["rfc460Timestamp"])
    det = get(FEED + "/details/" + gid, startingTime=fmt(floor10(tend - dt.timedelta(seconds=30))))
    frames = det.get("frames") or []
    last = frames[-1]
    byid = {p["participantId"]: p for p in last["participants"]}
    # one snapshot a minute through the game: gives the order items were first seen (build order) and the last trinket a player held
    from concurrent.futures import ThreadPoolExecutor
    mins = []
    m = 1
    while t0 + dt.timedelta(minutes=m) < tend: mins.append(m); m += 1
    def sample(m):
        st0 = fmt(floor10(t0 + dt.timedelta(minutes=m))); d = None; gd = None; st = None
        try: d = (get(FEED + "/details/" + gid, startingTime=st0).get("frames") or [{}])[0].get("participants") or []
        except Exception: pass
        try:
            f = (get(FEED + "/window/" + gid, startingTime=st0).get("frames") or [None])[0]
            if f: gd = [m, f["blueTeam"]["totalGold"] - f["redTeam"]["totalGold"]]; st = team_state(f)
        except Exception: pass
        return d, gd, st
    with ThreadPoolExecutor(4) as ex: res = list(ex.map(sample, mins))
    samples = [{q["participantId"]: [i for i in (q.get("items") or []) if i] for q in d} for d, _, _ in res if d is not None]
    gold = [[0, 0]] + [g for _, g, _ in res if g]
    states = [(0, [[0, 0, 0, []], [0, 0, 0, []]])] + [(m_, st_) for m_, (_, _, st_) in zip(mins, res) if st_] + [(round((tend - t0).total_seconds() / 60, 2), team_state(fr[-1]))]
    obj = obj_events(states)
    def order_of(pid):
        seen, out = set(), []
        for s in samples:
            for i in s.get(pid, []):
                if i not in seen: seen.add(i); out.append(i)
        return out
    def last_trinket(pid):
        for s in reversed(samples):
            tr = [i for i in s.get(pid, []) if i in TRINKET_IDS]
            if tr: return tr[0]
        return None
    players = {}
    for side in ("blue", "red"):
        for pm in md[side + "TeamMetadata"]["participantMetadata"]:
            p = byid.get(pm["participantId"]) or {}
            pos = ROLES.get(pm["role"])
            if not pos: continue
            perk = p.get("perkMetadata") or {}
            items = [i for i in (p.get("items") or []) if i]       # Riot lists stacked consumables once per charge; junglers sometimes sell the trinket, so none is a real state
            tr0 = None if any(i in TRINKET_IDS for i in items) else last_trinket(pm["participantId"])
            players[side + ":" + pos] = dict(name=pm.get("summonerName"), champ=pm.get("championId"), items=items, tr0=tr0, order=order_of(pm["participantId"]),
                                             runes=dict(style=perk.get("styleId"), sub=perk.get("subStyleId"), perks=perk.get("perks")))
    return dict(id=gid, v=FORMAT, number=number, bo=bo, codes=sorted(codes), start=fmt(t0), patch=md.get("patchVersion"), players=players, gold=gold, obj=obj)

def pick_leagues():
    """[(league id, slug, since)] for the slugs in LEAGUES that the schedule API knows, in priority order; logs the ones it does not."""
    leagues = get(GW + "/getLeagues", hl="en-US")["data"]["leagues"]
    by = {(l.get("slug") or "").lower(): l for l in leagues}
    out, seen = [], set()
    for slug, since in LEAGUES:
        l = by.get(slug)
        if l and l["id"] not in seen: seen.add(l["id"]); out.append((l["id"], l["slug"], since))
    print("leagues used:", ", ".join(x[1] for x in out) or "-")
    print("other leagues in the API (not used):", ", ".join(sorted(by.keys() - {x[1].lower() for x in out}))[:600])
    return out

def main():
    try: cache = json.loads(OUT.read_text(encoding="utf-8"))
    except Exception: cache = {}
    new = bad = 0; skipped = 0; t_start = time.time()
    try: done = json.loads(DONE.read_text(encoding="utf-8"))
    except Exception: done = {}
    lgs = pick_leagues()
    print("games already cached:", len(cache))
    for lid, slug, since in lgs:
        try: ms = finished_matches(lid, since)
        except Exception as ex: print("  league", slug, "schedule failed:", ex); continue
        print("  %s: %d finished matches" % (slug, len(ms)))
        for mid, e in sorted(ms.items(), key=lambda x: x[1]["startTime"], reverse=True):
            codes = [t["code"].upper() for t in e["match"]["teams"]]
            if done.get(mid) == FORMAT: continue
            if time.time() - t_start > BUDGET: skipped += 1; continue
            try: games = get(GW + "/getEventDetails", hl="en-US", id=mid)["data"]["event"]["match"]["games"]
            except Exception as ex: print("  match", mid, "details failed:", ex); bad += 1; continue
            bo = int(((e["match"].get("strategy") or {}).get("count")) or 0); ok = True
            for g in games:
                if g["id"] in cache and bo and not cache[g["id"]].get("bo"): cache[g["id"]]["bo"] = bo       # backfill best-of on older entries
                old = cache.get(g["id"])
                stale = bool(old) and (old.get("v", 1) < FORMAT or (old.get("lg") not in (None, "worlds") and "obj" not in old))
                if g.get("state") != "completed": ok = False; continue
                if old and not stale: continue
                if time.time() - t_start > BUDGET: skipped += 1; ok = False; continue          # keep the run short; the rest is picked up on the next run
                try:
                    cache[g["id"]] = fetch_game(g, g["number"], codes, bo); cache[g["id"]]["lg"] = slug; new += 1
                    OUT.parent.mkdir(exist_ok=True); OUT.write_text(json.dumps(cache, ensure_ascii=False))
                except Exception as ex: print("  game", g["id"], codes, "failed:", ex); bad += 1; ok = False
                time.sleep(0.3)
            if ok and games: done[mid] = FORMAT; DONE.write_text(json.dumps(done))
    OUT.parent.mkdir(exist_ok=True); OUT.write_text(json.dumps(cache, ensure_ascii=False))
    print("items: %d games cached (%d new, %d failed)%s" % (len(cache), new, bad, (" | %d games left for the next run (time budget)" % skipped) if skipped else ""))

if __name__ == "__main__":
    try: main()
    except Exception as e: print("item fetch failed (keeping what is cached):", repr(e), file=sys.stderr)
