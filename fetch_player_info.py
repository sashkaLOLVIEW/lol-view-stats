#!/usr/bin/env python3
"""Look up birthdate and contract end for every player on the site from Leaguepedia (lol.fandom.com, Cargo API).

    python fetch_player_info.py [path/to/csv]      -> config/player_info_auto.json  (+ a report in the log)

Never fails the build: on any error the previous data/player_info_auto.json is kept.
Hand-typed values in config/player_info.csv always win over these (merged in build.py).
"""
import json, re, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "config" / "player_info_auto.json"      # committed to the repository by .github/workflows/player-info.yml
API = "https://lol.fandom.com/api.php"
UA = "lol-view-stats fan site (github.com/sashkaLOLVIEW/lol-view-stats)"
BATCH = 20
REFRESH_DAYS = 7        # look a player up again after this many days

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

class RateLimited(Exception): pass

def main():
    import requests
    sys.path.insert(0, str(ROOT))
    import build
    csv = sys.argv[1] if len(sys.argv) > 1 else build.CSV_DEFAULT
    w = build.load_event(csv); pl = w[w.position != "team"]
    teams = {n: {n.lower(), build.need_code(n).lower()} for n in pl.teamname.unique()}
    players = sorted({(r.playername, r.teamname) for r in pl.itertuples()})
    try: old = json.loads(OUT.read_text(encoding="utf-8"))
    except Exception: old = {}
    now = time.time()
    todo = [p for p in players if now - (old.get(p[0]) or {}).get("ts", 0) > REFRESH_DAYS * 86400]
    print("%d players on the site, %d already looked up recently, %d to look up now" % (len(players), len(players) - len(todo), len(todo)))
    s = requests.Session(); s.headers["User-Agent"] = UA
    def get(**p):
        for attempt in range(5):                           # patient: wait and retry when the wiki says "ratelimited"
            r = s.get(API, params=dict(format="json", **p), timeout=60); r.raise_for_status(); d = r.json()
            if (d.get("error") or {}).get("code") != "ratelimited": return d
            wait = 30 * (attempt + 1); print("  rate limited, waiting %ds (attempt %d/5)" % (wait, attempt + 1)); time.sleep(wait)
        raise RateLimited()
    fl = get(action="cargofields", table="Players")
    cf = fl.get("cargofields") or {}
    fields = list(cf.keys()) if isinstance(cf, dict) else [f.get("fieldname", f) if isinstance(f, dict) else str(f) for f in cf]
    f_bd = find_field(fields, "birth"); f_ct = find_field(fields, "contract")
    print("using birthdate field:", f_bd, "| contract field:", f_ct)
    want = [f for f in ("ID", "Team", "IsRetired", f_bd, f_ct) if f and f in fields]
    out = dict(old); blocked = False
    for i in range(0, len(todo), BATCH):
        chunk = todo[i:i + BATCH]
        ids = ",".join("'" + n.replace("'", "\\'") + "'" for n, _ in chunk)
        try: d = get(action="cargoquery", tables="Players", fields=",".join(want), where="ID IN (%s)" % ids, limit=500)
        except RateLimited: blocked = True; print("  still rate limited - stopping; the rest is tried again on the next run"); break
        if d.get("error"): print("wiki error:", json.dumps(d["error"])[:300]); continue
        by = {}
        for row in d.get("cargoquery", []):
            t = row.get("title", row); by.setdefault((t.get("ID") or "").lower(), []).append(t)
        for name, team in chunk:
            r = pick(by.get(name.lower(), []), teams[team])
            if not r: out[name] = dict(bd=None, contract=None, ts=now, nomatch=True); continue
            bd = (r.get(f_bd) or "").strip() if f_bd else ""; ct = month_year((r.get(f_ct) or "").strip()) if f_ct else None
            out[name] = dict(bd=bd if re.match(r"\d{4}-\d{2}-\d{2}", bd) else None, contract=ct, ts=now)
        time.sleep(25)                                     # be gentle: the wiki limits bursts
    OUT.parent.mkdir(exist_ok=True); OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1))
    mine = {n: out.get(n) for n, _ in players}
    have = {n: v for n, v in mine.items() if v and not v.get("nomatch")}
    print("player info: %d of %d players found | %d birthdates | %d contract dates | %d without a wiki match | %d not looked up yet" % (
        len(have), len(players), sum(1 for v in have.values() if v["bd"]), sum(1 for v in have.values() if v["contract"]),
        sum(1 for v in mine.values() if v and v.get("nomatch")), sum(1 for v in mine.values() if v is None)))
    print("no contract date:", ", ".join(sorted(n for n, v in have.items() if not v["contract"])) or "-")
    print("no birthdate:", ", ".join(sorted(n for n, v in have.items() if not v["bd"])) or "-")
    print("not matched:", ", ".join(sorted(n for n, v in mine.items() if v and v.get("nomatch"))) or "-")
    if blocked: print("NOTE: the wiki limited us; run the workflow again in a few minutes to fetch the rest.")

if __name__ == "__main__":
    try: main()
    except Exception as e:
        print("player info fetch failed (keeping the previous file):", repr(e), file=sys.stderr)
