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
KEY = os.environ.get("LOLESPORTS_API_KEY", "").strip() or "0TvQnueqKa5mxJntVWt0w4LpLfEkrV1Ta8rQBb9Z"
GW = "https://esports-api.lolesports.com/persisted/gw"
FEED = "https://feed.lolesports.com/livestats/v1"
H = {"x-api-key": KEY, "User-Agent": "lol-view-stats fan site"}
LEAGUE_SLUG = "worlds"            # lolesports slug of the event shown on the site
SINCE = "2026-10-22"              # ignore matches before this date (the Worlds main stage starts on 2026-10-23)
MAX_PAGES = 6
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

def iso(s): return dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
def fmt(t): return t.strftime("%Y-%m-%dT%H:%M:%S.000Z")
def floor10(t): return t.replace(second=t.second - t.second % 10, microsecond=0)

def finished_matches():
    leagues = get(GW + "/getLeagues", hl="en-US")["data"]["leagues"]
    lid = next(l["id"] for l in leagues if l.get("slug") == LEAGUE_SLUG)
    out, token = {}, None
    for _ in range(MAX_PAGES):
        p = dict(hl="en-US", leagueId=lid)
        if token: p["pageToken"] = token
        sch = get(GW + "/getSchedule", **p)["data"]["schedule"]
        evs = sch.get("events") or []
        for e in evs:
            if e.get("state") == "completed" and e.get("match") and (e.get("startTime") or "")[:10] >= SINCE:
                out[e["match"]["id"]] = e
        old = [e for e in evs if e.get("startTime")]
        token = (sch.get("pages") or {}).get("older")
        if not token or (old and min(e["startTime"] for e in old)[:10] < SINCE): break
    return out

def fetch_game(game, number, codes, bo=0):
    gid = game["id"]
    w0 = get(FEED + "/window/" + gid)
    md = w0["gameMetadata"]; t0 = iso(w0["frames"][0]["rfc460Timestamp"])
    wend = get(FEED + "/window/" + gid, startingTime=fmt(floor10(t0 + dt.timedelta(hours=3))))
    fr = wend.get("frames") or []
    if not fr or fr[-1].get("gameState") != "finished": raise RuntimeError("no finished frame")
    tend = iso(fr[-1]["rfc460Timestamp"])
    det = get(FEED + "/details/" + gid, startingTime=fmt(floor10(tend - dt.timedelta(seconds=30))))
    frames = det.get("frames") or []
    last = frames[-1]
    byid = {p["participantId"]: p for p in last["participants"]}
    # one snapshot a minute through the game: gives the order items were first seen (build order) and the last trinket a player held
    samples = []
    m = 1
    while t0 + dt.timedelta(minutes=m) < tend:
        try:
            d = (get(FEED + "/details/" + gid, startingTime=fmt(floor10(t0 + dt.timedelta(minutes=m)))).get("frames") or [{}])[0].get("participants") or []
            samples.append({q["participantId"]: [i for i in (q.get("items") or []) if i] for q in d})
        except Exception: pass
        m += 1; time.sleep(0.12)
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
    return dict(id=gid, v=FORMAT, number=number, bo=bo, codes=sorted(codes), start=fmt(t0), patch=md.get("patchVersion"), players=players)

def main():
    try: cache = json.loads(OUT.read_text(encoding="utf-8"))
    except Exception: cache = {}
    ms = finished_matches(); new = bad = 0
    print("finished matches:", len(ms), "| games already cached:", len(cache))
    t_start = time.time(); skipped = 0
    for mid, e in sorted(ms.items(), key=lambda x: x[1]["startTime"]):
        codes = [t["code"].upper() for t in e["match"]["teams"]]
        try: games = get(GW + "/getEventDetails", hl="en-US", id=mid)["data"]["event"]["match"]["games"]
        except Exception as ex: print("  match", mid, "details failed:", ex); bad += 1; continue
        bo = int(((e["match"].get("strategy") or {}).get("count")) or 0)
        for g in games:
            if g["id"] in cache and bo and not cache[g["id"]].get("bo"): cache[g["id"]]["bo"] = bo       # backfill best-of on older entries
            old = cache.get(g["id"])
            stale = bool(old) and old.get("v", 1) < FORMAT
            if g.get("state") != "completed" or (old and not stale): continue
            if time.time() - t_start > BUDGET: skipped += 1; continue          # keep the run short; the rest is picked up on the next run
            try: cache[g["id"]] = fetch_game(g, g["number"], codes, bo); new += 1; OUT.parent.mkdir(exist_ok=True); OUT.write_text(json.dumps(cache, ensure_ascii=False))
            except Exception as ex: print("  game", g["id"], codes, "failed:", ex); bad += 1
            time.sleep(0.3)
    OUT.parent.mkdir(exist_ok=True); OUT.write_text(json.dumps(cache, ensure_ascii=False))
    print("items: %d games cached (%d new, %d failed)%s" % (len(cache), new, bad, (" | %d games left for the next run (time budget)" % skipped) if skipped else ""))

if __name__ == "__main__":
    try: main()
    except Exception as e: print("item fetch failed (keeping what is cached):", repr(e), file=sys.stderr)
