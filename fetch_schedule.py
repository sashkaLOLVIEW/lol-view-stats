#!/usr/bin/env python3
"""Download upcoming matches from the (unofficial) lolesports schedule feed into data/schedule.json.

    python fetch_schedule.py

The feed is the one lolesports.com itself uses. It is not documented or supported by Riot, so this script is
defensive: any failure leaves the previous data/schedule.json untouched and exits 0 (the site just keeps
showing the last good list).  The key below is the public one that lolesports.com sends from every browser;
set LOLESPORTS_API_KEY to override it.
"""
import json, os, sys, time
from pathlib import Path

BASE = "https://esports-api.lolesports.com/persisted/gw/getSchedule"
KEY = os.environ.get("LOLESPORTS_API_KEY", "").strip() or "0TvQnueqKa5mxJntVWt0w4LpLfEkrV1Ta8rQBb9Z"
OUT = Path(__file__).resolve().parent / "data" / "schedule.json"
MAX_PAGES = 8          # pages of "newer" events to follow
KEEP = 60              # upcoming matches to keep in total

# lolesports league slug -> filter key.  Anything not listed is ignored (challengers, academy, ...).
LEAGUES = {"worlds": "worlds", "msi": "intl", "first_stand": "intl", "esports-world-cup": "intl", "ewc": "intl",
           "lck": "lck", "lpl": "lpl", "lec": "lec", "lcs": "lcs", "cblol-brazil": "cblol", "cblol": "cblol", "lcp": "lcp"}

def parse(payload):
    """Pull the unstarted matches out of one getSchedule response. Returns (matches, newer_token)."""
    sch = (payload.get("data") or {}).get("schedule") or {}
    out = []
    for ev in sch.get("events") or []:
        m = ev.get("match") or {}
        teams = m.get("teams") or []
        if ev.get("type") != "match" or ev.get("state") != "unstarted" or len(teams) != 2: continue
        slug = ((ev.get("league") or {}).get("slug") or "").lower()
        if slug not in LEAGUES: continue
        codes = [(t.get("code") or "").upper() or "TBD" for t in teams]      # undecided teams stay in as TBD placeholders
        strat = m.get("strategy") or {}
        out.append(dict(start=ev.get("startTime"), league=LEAGUES[slug], home=codes[0], away=codes[1],
                        home_name=teams[0].get("name"), away_name=teams[1].get("name"), bo=int(strat.get("count") or 1)))
    return out, (sch.get("pages") or {}).get("newer")

def main():
    import requests
    got, token, seen = [], None, set()
    for _ in range(MAX_PAGES):
        params = {"hl": "en-US"}
        if token: params["pageToken"] = token
        r = requests.get(BASE, params=params, headers={"x-api-key": KEY}, timeout=30)
        r.raise_for_status()
        ms, token = parse(r.json())
        for m in ms:
            k = (m["start"], m["home"], m["away"])
            if k not in seen: seen.add(k); got.append(m)
        if not token or len(got) >= KEEP: break
        time.sleep(0.5)
    got.sort(key=lambda m: m["start"])
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(dict(fetched=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), matches=got[:KEEP]), ensure_ascii=False))
    print("schedule: kept %d upcoming matches" % len(got[:KEEP]))

if __name__ == "__main__":
    try: main()
    except Exception as e:                                # never fail the whole site because the schedule is down
        print("schedule fetch failed (keeping the previous list):", e, file=sys.stderr)
