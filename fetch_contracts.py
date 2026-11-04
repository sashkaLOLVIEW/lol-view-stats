#!/usr/bin/env python3
"""Download the published contract spreadsheet (Google Sheets "publish to web" CSV) -> config/contracts_auto.json

    python fetch_contracts.py

The sheet layout is not fixed: the header row is found by looking for a player/name column and a contract-end/expiry column.
Never fails the build: on any error the previous file is kept. Hand-typed values in config/player_info.csv still win (build.py).
"""
import csv, io, json, re, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "config" / "contracts_auto.json"
SHEET = "1Y7k5kQ2AegbuyiGwEPsa62e883FYVtHqr6UVut9RC4o"
TABS = {"LPL": "594163931", "LCK": "905624073", "LCP": "1177719586", "LEC": "148326031", "LCS": "0"}      # league -> tab (gid) of the published sheet
URL = "https://docs.google.com/spreadsheets/d/%s/pub?gid=%%s&single=true&output=csv" % SHEET
UA = "lol-view-stats fan site (github.com/sashkaLOLVIEW/lol-view-stats)"

def col(header, *needles, avoid=()):
    for n in needles:
        for i, h in enumerate(header):
            hl = h.lower()
            if n in hl and not any(a in hl for a in avoid): return i
    return None

def norm_date(v):
    v = (v or "").strip()
    if not v or v in ("-", "—", "N/A", "n/a", "TBD", "tbd"): return None
    try:
        import pandas as pd
        t = pd.to_datetime(v, errors="coerce", dayfirst=False)
        if not pd.isna(t): return t.strftime("%Y-%m-%d")
    except Exception: pass
    return v                       # keep the raw text (e.g. "End of 2026") rather than drop it

def read_tab(requests, league, gid):
    r = requests.get(URL % gid, headers={"User-Agent": UA}, timeout=60); r.raise_for_status()
    rows = list(csv.reader(io.StringIO(r.content.decode("utf-8", "replace"))))
    print("%s: downloaded %d rows" % (league, len(rows)))
    hi = None
    for i, row in enumerate(rows[:15]):
        p = col(row, "player", "ign", "summoner", "name", avoid=("team", "legal")); e = col(row, "expir", "contract end", "end date", "ends", "until", "end")
        if p is not None and e is not None: hi, ip, ie = i, p, e; break
    if hi is None:
        print("  could not find the header row; first rows:"); [print("    ", x[:10]) for x in rows[:6]]; return []
    h = rows[hi]; it = col(h, "team", "org", avoid=("contact",)); ir = col(h, "role", "position"); itc = col(h, "tri")
    print("  header row %d: player=%r team=%r role=%r tri=%r end=%r" % (hi, h[ip], h[it] if it is not None else None, h[ir] if ir is not None else None, h[itc] if itc is not None else None, h[ie]))
    got = lambda row, i: (row[i].strip() if i is not None and i < len(row) else "")
    out = []
    for row in rows[hi + 1:]:
        if len(row) <= max(ip, ie) or not row[ip].strip(): continue
        out.append(dict(league=league, player=row[ip].strip(), team=got(row, it), tri=got(row, itc), role=got(row, ir), raw_end=row[ie].strip(), contract=norm_date(row[ie])))
    return out

def main():
    import requests
    rows, players = [], {}
    for league, gid in TABS.items():
        try: got = read_tab(requests, league, gid)
        except Exception as e: print("  %s failed: %r" % (league, e)); continue
        rows += got
        for r in got:
            if r["contract"] and r["player"].lower() not in {k.lower() for k in players}: players[r["player"]] = {"contract": r["contract"], "team": r["team"], "league": r["league"]}
    if not rows: print("nothing downloaded - keeping the previous file"); return
    OUT.write_text(json.dumps({"fetched": time.time(), "players": players, "rows": rows}, ensure_ascii=False, indent=1))
    print("%d rows, %d players with a contract end date saved" % (len(rows), len(players)))
    print("per league:", {l: sum(1 for r in rows if r["league"] == l) for l in TABS})

if __name__ == "__main__":
    try: main()
    except Exception as e: print("contract sheet fetch failed (keeping the previous file):", repr(e), file=sys.stderr)
