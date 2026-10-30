#!/usr/bin/env python3
"""Look up birthdate and contract end for every player on the site from Leaguepedia (lol.fandom.com, Cargo API).

    python fetch_player_info.py [path/to/csv]      -> data/player_info_auto.json  (+ a report in the log)

Never fails the build: on any error the previous data/player_info_auto.json is kept.
Hand-typed values in config/player_info.csv always win over these (merged in build.py).
"""
import json, re, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "data" / "player_info_auto.json"
API = "https://lol.fandom.com/api.php"
UA = "lol-view-stats fan site (github.com/sashkaLOLVIEW/lol-view-stats)"
BATCH = 20

def find_field(fields, *needles):
    for n in needles:
        for f in fields:
            if n in f.lower(): return f
    return None

def month_year(s):
    m = re.match(r"(\d{4})-(\d{2})", s or "")
    return None if not m else ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"][int(m.group(2)) - 1] + " " + m.group(1)

def pick(rows, team_names):
    """Several wiki pages can share one in-game name; prefer the active player on our team."""
    act = [r for r in rows if str(r.get("IsRetired", "")).lower() not in ("yes", "1", "true")] or rows
    on = [r for r in act if (r.get("Team") or "").lower() in team_names]
    for c in (on, act):
        if len(c) == 1: return c[0]
    return None

def main():
    import requests
    sys.path.insert(0, str(ROOT))
    import build
    csv = sys.argv[1] if len(sys.argv) > 1 else build.CSV_DEFAULT
    w = build.load_event(csv); pl = w[w.position != "team"]
    teams = {n: {n.lower(), build.need_code(n).lower()} for n in pl.teamname.unique()}
    players = sorted({(r.playername, r.teamname) for r in pl.itertuples()})
    s = requests.Session(); s.headers["User-Agent"] = UA
    def get(**p):
        r = s.get(API, params=dict(format="json", **p), timeout=60); r.raise_for_status(); return r.json()
    fl = get(action="cargofields", table="Players")
    cf = fl.get("cargofields") or {}
    fields = list(cf.keys()) if isinstance(cf, dict) else [f.get("fieldname", f) if isinstance(f, dict) else str(f) for f in cf]
    print("Players table fields:", ", ".join(fields))
    f_bd = find_field(fields, "birth"); f_ct = find_field(fields, "contract")
    print("using birthdate field:", f_bd, "| contract field:", f_ct)
    want = [f for f in ("ID", "Team", "IsRetired", f_bd, f_ct) if f and f in fields]
    out, missing = {}, []
    for i in range(0, len(players), BATCH):
        chunk = players[i:i + BATCH]
        ids = ",".join("'" + n.replace("'", "\\'") + "'" for n, _ in chunk)
        def query(where):
            d = get(action="cargoquery", tables="Players", fields=",".join(want), where=where, limit=500)
            if i == 0 and where.startswith("ID IN"): print("first batch raw reply:", json.dumps(d, ensure_ascii=False)[:700])
            if d.get("error"): print("wiki error:", json.dumps(d["error"])[:300])
            return d.get("cargoquery", [])
        rows = query("ID IN (%s)" % ids)
        if not rows:                                       # retry one name at a time
            for n, _ in chunk:
                rows += query("ID='%s'" % n.replace("'", "\\'")); time.sleep(1)
        by = {}
        for row in rows:
            t = row.get("title", row); by.setdefault((t.get("ID") or "").lower(), []).append(t)
        for name, team in chunk:
            r = pick(by.get(name.lower(), []), teams[team])
            if not r: missing.append(name + " (no unique wiki match)"); continue
            bd = (r.get(f_bd) or "").strip() if f_bd else ""; ct = month_year((r.get(f_ct) or "").strip()) if f_ct else None
            out[name] = dict(bd=bd if re.match(r"\d{4}-\d{2}-\d{2}", bd) else None, contract=ct)
        time.sleep(2)
    OUT.parent.mkdir(exist_ok=True); OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1))
    nb = sum(1 for v in out.values() if v["bd"]); nc = sum(1 for v in out.values() if v["contract"])
    print("player info: %d players looked up | %d birthdates | %d contract dates | %d without a wiki match" % (len(out), nb, nc, len(missing)))
    print("no contract date:", ", ".join(sorted(n for n, v in out.items() if not v["contract"])) or "-")
    print("no birthdate:", ", ".join(sorted(n for n, v in out.items() if not v["bd"])) or "-")
    print("not matched:", ", ".join(missing) or "-")

if __name__ == "__main__":
    try: main()
    except Exception as e:
        print("player info fetch failed (keeping the previous file):", repr(e), file=sys.stderr)
