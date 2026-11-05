#!/usr/bin/env python3
"""Download the roster spreadsheet (the site's reference for birthdates, countries, contract ends and coaches) -> config/roster_sheet.json

    python fetch_roster_sheet.py                 # downloads the Google Sheet as CSV (it must be shared as "Anyone with the link can view")
    python fetch_roster_sheet.py --file my.csv   # or read a CSV you already have

Columns: TEAM, ROLE, PLAYER, D.O.B, Country, Contract Expiry. Blank rows between teams are ignored.
Contract Expiry: a date or text is kept as written; "-" means "looked, not found"; "N/A" means "not needed" (nothing is shown).
Never fails the build: on any error the previous config/roster_sheet.json is kept.
"""
import csv, io, json, os, re, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "config" / "roster_sheet.json"
SHEET_ID = os.environ.get("ROSTER_SHEET_ID", "").strip() or "1MEN3QOOgbCmhHiNw-g_Fc71uu2XYrfzbnS5ByBcYbQc"
URL = os.environ.get("ROSTER_SHEET_URL", "").strip() or "https://docs.google.com/spreadsheets/d/%s/export?format=csv&gid=0" % SHEET_ID
UA = "lol-view-stats fan site (github.com/sashkaLOLVIEW/lol-view-stats)"

def parse(text):
    rows = list(csv.reader(io.StringIO(text)))
    if not rows: return None
    h = [c.strip().lower() for c in rows[0]]
    def ix(*names):
        for n in names:
            for i, c in enumerate(h):
                if n in c: return i
        return None
    it, ir, ip, ib, ic, ie = ix("team"), ix("role"), ix("player"), ix("d.o.b", "birth", "dob"), ix("country"), ix("contract", "expir")
    if ip is None or it is None: return None
    g = lambda r, i: (r[i].strip() if i is not None and i < len(r) else "")
    players, coaches = {}, {}
    for r in rows[1:]:
        name = g(r, ip)
        if not name: continue
        team, role = g(r, it), g(r, ir)
        bd = g(r, ib); bd = bd if re.match(r"\d{4}-\d{2}-\d{2}$", bd) else None
        rec = dict(team=team, role=role, bd=bd, cc=g(r, ic) or None, contract=g(r, ie) or None)
        if "coach" in role.lower():
            cur = coaches.get(team)
            if cur is None or ("head" in role.lower() and "head" not in cur["role"].lower()):
                coaches[team] = dict(name=name, cc=rec["cc"], role=role)
            continue
        players.setdefault(name, []).append(rec)
    return {"fetched": time.time(), "players": players, "coaches": coaches}

def main():
    if "--file" in sys.argv: text = Path(sys.argv[sys.argv.index("--file") + 1]).read_text(encoding="utf-8")
    else:
        import requests
        r = requests.get(URL, headers={"User-Agent": UA}, timeout=60); r.raise_for_status()
        text = r.content.decode("utf-8", "replace")
        if text.lstrip().lower().startswith("<!doctype html") or "<html" in text[:200].lower():
            print("the sheet did not come back as CSV - is it shared as 'Anyone with the link can view'? keeping the previous file"); return
    d = parse(text)
    if not d or not d["players"]: print("no player rows found - keeping the previous file"); return
    OUT.write_text(json.dumps(d, ensure_ascii=False, indent=1))
    n = sum(len(v) for v in d["players"].values())
    print("roster sheet: %d player rows (%d names), %d coaches, %d birthdates, %d countries, %d contracts" % (n, len(d["players"]), len(d["coaches"]),
          sum(1 for v in d["players"].values() for x in v if x["bd"]), sum(1 for v in d["players"].values() for x in v if x["cc"]), sum(1 for v in d["players"].values() for x in v if x["contract"])))

if __name__ == "__main__":
    try: main()
    except Exception as e: print("roster sheet fetch failed (keeping the previous file):", repr(e), file=sys.stderr)
