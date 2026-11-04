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
GID = "594163931"
URL = "https://docs.google.com/spreadsheets/d/%s/pub?gid=%s&single=true&output=csv" % (SHEET, GID)
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

def main():
    import requests
    r = requests.get(URL, headers={"User-Agent": UA}, timeout=60); r.raise_for_status()
    rows = list(csv.reader(io.StringIO(r.content.decode("utf-8", "replace"))))
    print("downloaded %d rows" % len(rows))
    hi = ip = ie = it = None
    for i, row in enumerate(rows[:15]):
        p = col(row, "player", "ign", "summoner", "name", avoid=("team",)); e = col(row, "expir", "contract end", "end date", "ends", "until", "end")
        if p is not None and e is not None: hi, ip, ie, it = i, p, e, col(row, "team", "org"); break
    if hi is None:
        print("could not find the header row; first rows:"); [print("  ", x[:10]) for x in rows[:8]]; return
    print("header row %d: %s | player col=%s team col=%s end col=%s" % (hi, rows[hi][:14], rows[hi][ip], rows[hi][it] if it is not None else None, rows[hi][ie]))
    out, seen = {}, set()
    for row in rows[hi + 1:]:
        if len(row) <= max(ip, ie) or not row[ip].strip(): continue
        name = row[ip].strip(); date = norm_date(row[ie])
        if not date: continue
        key = name.lower()
        if key in seen: print("  duplicate name, keeping the first:", name); continue
        seen.add(key); out[name] = {"contract": date, "team": (row[it].strip() if it is not None and it < len(row) else None)}
    OUT.write_text(json.dumps({"fetched": time.time(), "source": URL, "players": out}, ensure_ascii=False, indent=1))
    print("%d players with a contract end date saved" % len(out))
    print("sample:", ", ".join("%s=%s" % (k, v["contract"]) for k, v in list(out.items())[:8]))

if __name__ == "__main__":
    try: main()
    except Exception as e: print("contract sheet fetch failed (keeping the previous file):", repr(e), file=sys.stderr)
