#!/usr/bin/env python3
"""Pull every LPL team's roster (players, subs, coaches) from Leaguepedia (lol.fandom.com Cargo API).

    python fetch_lpl_rosters.py [path/to/csv]   -> config/lpl_roster_auto.json

Takes every field the wiki's Players table has except pictures (image / logo / photo / file fields are skipped).
LPL team names come from the Oracle's Elixir CSV (league == LPL). Never fails the build: on any error the previous file is kept.
Hand-typed values in config/player_info.csv and config/team_info.csv always win (merged in build.py).
"""
import json, re, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "config" / "lpl_roster_auto.json"
API = "https://lol.fandom.com/api.php"
UA = "lol-view-stats fan site (github.com/sashkaLOLVIEW/lol-view-stats)"
SKIP = re.compile(r"image|img|photo|logo|picture|file|icon|banner|signature|avatar", re.I)
BATCH = 10

def find_field(fields, *needles):
    for n in needles:
        for f in fields:
            if n in f.lower(): return f
    return None

def truthy(v): return str(v or "").strip().lower() in ("yes", "1", "true")

def normalise(raw, f):
    """Turn one wiki row into the few keys the site uses."""
    role = (raw.get(f["role"]) or "").strip() if f["role"] else ""
    low = role.lower()
    sub = truthy(raw.get(f["sub"])) if f["sub"] else False
    kind = "coach" if "coach" in low else "sub" if (sub or "sub" in low) else "starter"
    bd = (raw.get(f["bd"]) or "").strip() if f["bd"] else ""
    return dict(id=(raw.get("ID") or "").strip(), role=role, kind=kind,
                bd=bd if re.match(r"\d{4}-\d{2}-\d{2}", bd) else None,
                cc=((raw.get(f["cc"]) or "").split(",")[0].strip() or None) if f["cc"] else None,
                contract=(raw.get(f["ct"]) or "").strip() or None if f["ct"] else None,
                name=(raw.get(f["name"]) or "").strip() or None if f["name"] else None,
                retired=truthy(raw.get(f["ret"])) if f["ret"] else False, raw=raw)

def main():
    import requests
    sys.path.insert(0, str(ROOT))
    import build
    csv = sys.argv[1] if len(sys.argv) > 1 else build.CSV_DEFAULT
    import pandas as pd
    d = pd.read_csv(csv, low_memory=False, usecols=["league", "teamname", "year"])
    lpl = sorted(d[(d.league == "LPL") & (d.year == 2026)].teamname.dropna().unique())
    print("%d LPL teams in the match data: %s" % (len(lpl), ", ".join(lpl)))
    if not lpl: print("no LPL teams found - nothing to do"); return
    s = requests.Session(); s.headers["User-Agent"] = UA
    def get(**p):
        for attempt in range(5):
            r = s.get(API, params=dict(format="json", **p), timeout=60); r.raise_for_status(); j = r.json()
            if (j.get("error") or {}).get("code") != "ratelimited": return j
            wait = 30 * (attempt + 1); print("  rate limited, waiting %ds" % wait); time.sleep(wait)
        raise RuntimeError("rate limited")
    cf = get(action="cargofields", table="Players").get("cargofields") or {}
    fields = list(cf.keys()) if isinstance(cf, dict) else [x.get("fieldname", x) if isinstance(x, dict) else str(x) for x in cf]
    f = dict(bd=find_field(fields, "birth"), ct=find_field(fields, "contract"), cc=find_field(fields, "nationalityprimary", "country", "nationality"),
             role=find_field(fields, "role"), sub=find_field(fields, "issubstitute", "substitute"), name=find_field(fields, "name"),
             ret=find_field(fields, "isretired"))
    f["name"] = "Name" if "Name" in fields else f["name"]
    want = [x for x in fields if not SKIP.search(x)]
    for must in ("ID", "Team"):
        if must in fields and must not in want: want.append(must)
    print("fields used (%d of %d, pictures skipped): %s" % (len(want), len(fields), ", ".join(want)))
    print("mapped:", {k: v for k, v in f.items()})
    teams = {}
    for i in range(0, len(lpl), BATCH):
        chunk = lpl[i:i + BATCH]; names = ",".join("'" + n.replace("'", "\\'") + "'" for n in chunk); off = 0
        while True:
            j = get(action="cargoquery", tables="Players", fields=",".join(want), where="Team IN (%s)" % names, limit=500, offset=off)
            if j.get("error"): print("wiki error:", json.dumps(j["error"])[:300]); break
            rows = [r.get("title", r) for r in j.get("cargoquery", [])]
            for raw in rows:
                p = normalise(raw, f)
                if p["retired"] and p["kind"] != "coach": continue
                teams.setdefault((raw.get("Team") or "").strip(), []).append(p)
            if len(rows) < 500: break
            off += 500
        time.sleep(20)
    missing = [n for n in lpl if n not in teams]
    out = {"fetched": time.time(), "fields": want, "teams": {t: sorted(v, key=lambda p: (p["kind"] != "starter", p["role"], p["id"])) for t, v in sorted(teams.items())}}
    OUT.parent.mkdir(exist_ok=True); OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1))
    for t, v in out["teams"].items():
        k = lambda kind: ", ".join(p["id"] for p in v if p["kind"] == kind) or "-"
        print("%s | starters: %s | subs: %s | coaches: %s" % (t, k("starter"), k("sub"), k("coach")))
    print("no birthdate:", ", ".join(sorted(p["id"] for v in teams.values() for p in v if not p["bd"] and p["kind"] != "coach")) or "-")
    print("no country:", ", ".join(sorted(p["id"] for v in teams.values() for p in v if not p["cc"])) or "-")
    print("teams with no wiki match:", ", ".join(missing) or "-")

if __name__ == "__main__":
    try: main()
    except Exception as e:
        print("LPL roster fetch failed (keeping the previous file):", repr(e), file=sys.stderr)
