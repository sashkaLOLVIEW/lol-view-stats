#!/usr/bin/env python3
"""One-off diagnostic: walks Riot's lolesports feeds for ONE finished Worlds game and prints what each step returns.
Run it from the 'Probe Riot feed' workflow; the log tells us how to fetch item builds. Changes nothing."""
import json, os, sys, datetime as dt
import requests

KEY = os.environ.get("LOLESPORTS_API_KEY", "").strip() or "0TvQnueqKa5mxJntVWt0w4LpLfEkrV1Ta8rQBb9Z"
GW = "https://esports-api.lolesports.com/persisted/gw"
FEED = "https://feed.lolesports.com/livestats/v1"
H = {"x-api-key": KEY, "User-Agent": "lol-view-stats probe"}

def get(url, **params):
    try:
        r = requests.get(url, params=params, headers=H, timeout=30)
        ct = r.headers.get("content-type", "")
        print("  GET", url.replace(GW, "gw").replace(FEED, "feed"), {k: v for k, v in params.items() if k != "hl"}, "->", r.status_code, ct.split(";")[0], len(r.content), "bytes")
        if r.status_code != 200: print("   body:", r.text[:300].replace("\n", " ")); return None
        return r.json()
    except Exception as e:
        print("  request failed:", repr(e)); return None

def keys(d, n=40): return list(d.keys())[:n] if isinstance(d, dict) else type(d).__name__

def step(t): print("\n== " + t)

step("1. leagues")
j = get(GW + "/getLeagues", hl="en-US")
lg = ((j or {}).get("data") or {}).get("leagues") or []
print("  leagues:", len(lg), [l.get("slug") for l in lg][:30])
w = next((l for l in lg if l.get("slug") == "worlds"), None)
print("  worlds league:", w and {k: w[k] for k in ("id", "slug", "name")})

step("2. schedule (worlds)")
ev = []
if w:
    j = get(GW + "/getSchedule", hl="en-US", leagueId=w["id"])
    sch = ((j or {}).get("data") or {}).get("schedule") or {}
    ev = sch.get("events") or []
    print("  pages:", sch.get("pages"), "| events:", len(ev), "| states:", sorted({(e.get('state'), e.get('type')) for e in ev}))
done = [e for e in ev if e.get("state") == "completed" and e.get("match")]
print("  completed matches in this page:", len(done))
m = done[-1] if done else None
if m: print("  using match:", m["match"].get("id"), [t.get("code") for t in m["match"].get("teams", [])], m.get("startTime"), "keys:", keys(m["match"]))

step("3. event details -> games")
games = []
if m:
    j = get(GW + "/getEventDetails", hl="en-US", id=m["match"]["id"])
    ev0 = ((j or {}).get("data") or {}).get("event") or {}
    games = (ev0.get("match") or {}).get("games") or []
    print("  event keys:", keys(ev0), "| games:", [(g.get("number"), g.get("id"), g.get("state")) for g in games])
    if games: print("  game[0] keys:", keys(games[0]), "| teams:", games[0].get("teams"))

step("4. live stats window")
g = next((x for x in games if x.get("state") == "completed"), None)
if g:
    gid = g["id"]
    j = get(FEED + "/window/" + gid)
    if j:
        print("  window keys:", keys(j)); md = j.get("gameMetadata") or {}
        print("  gameMetadata keys:", keys(md), "| patch:", md.get("patchVersion"))
        bm = (md.get("blueTeamMetadata") or {})
        print("  blue metadata keys:", keys(bm), "| participant[0]:", json.dumps((bm.get("participantMetadata") or [{}])[0])[:300])
        fr = j.get("frames") or []
        print("  frames:", len(fr), "| first:", fr[0].get("rfc460Timestamp") if fr else None, "| last:", fr[-1].get("rfc460Timestamp") if fr else None, "| state:", fr[-1].get("gameState") if fr else None)
        if fr: print("  frame keys:", keys(fr[0]), "| blue keys:", keys(fr[0].get("blueTeam")), "| player[0]:", json.dumps(((fr[0].get("blueTeam") or {}).get("participants") or [{}])[0])[:300])
        t0 = dt.datetime.fromisoformat(fr[0]["rfc460Timestamp"].replace("Z", "+00:00")) if fr else None
    else: t0 = None

    step("5. final frame (try several start times)")
    if t0:
        for mins in (20, 30, 45):
            t = t0 + dt.timedelta(minutes=mins); t = t.replace(second=t.second - t.second % 10, microsecond=0)
            jj = get(FEED + "/window/" + gid, startingTime=t.strftime("%Y-%m-%dT%H:%M:%S.000Z"))
            if jj:
                f2 = jj.get("frames") or []
                print("   frames:", len(f2), "| last state:", f2[-1].get("gameState") if f2 else None, "| last ts:", f2[-1].get("rfc460Timestamp") if f2 else None)

    step("6. details (items / runes)")
    if t0:
        t = t0 + dt.timedelta(minutes=20); t = t.replace(second=t.second - t.second % 10, microsecond=0)
        jd = get(FEED + "/details/" + gid, startingTime=t.strftime("%Y-%m-%dT%H:%M:%S.000Z"))
        if jd:
            f3 = jd.get("frames") or []
            print("  details keys:", keys(jd), "| frames:", len(f3))
            if f3: print("  participant[0]:", json.dumps((f3[-1].get("participants") or [{}])[0])[:700])
print("\nprobe finished")
