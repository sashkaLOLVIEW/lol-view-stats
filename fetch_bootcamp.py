#!/usr/bin/env python3
"""SoloQ stats of the event's players, for the Bootcamp page.

    python fetch_bootcamp.py       -> data/soloq_accounts.json (accounts found on Leaguepedia) + data/bootcamp.json (rank, recent games per account)

* Accounts: config/soloq_accounts.csv (hand-typed: player,account  e.g.  Faker,Hide on bush#KR1 - region optional: KR: Hide on bush#KR1) wins;
  otherwise the SoloqueueIds field of the player's Leaguepedia page (lol.fandom.com, Cargo API) is used. Accounts without a #tag cannot be looked up.
* Stats: Riot's official API (needs the repository secret RIOT_API_KEY). Without a key the script just exits and the page says so.
* Polite: spreads requests out (dev keys allow ~100 per 2 minutes), refreshes the stalest accounts first and stops after BUDGET seconds.
Never fails the build: on any error the previous data/bootcamp.json is kept.
"""
import csv, json, os, re, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ACC = ROOT / "data" / "soloq_accounts.json"
OUT = ROOT / "data" / "bootcamp.json"
MANUAL = ROOT / "config" / "soloq_accounts.csv"
KEY = os.environ.get("RIOT_API_KEY", "").strip()
UA = "lol-view-stats fan site (github.com/sashkaLOLVIEW/lol-view-stats)"
BUDGET = int(os.environ.get("BOOTCAMP_BUDGET", "330"))      # seconds of Riot requests per run
MIN_AGE = 45 * 60            # an account is refreshed again after this many seconds
ACC_REFRESH_DAYS = 14
GAP = float(os.environ.get("RIOT_GAP", "1.3"))             # seconds between Riot requests (dev key: 100 per 2 minutes)
RECENT = 8                   # soloQ games looked at per account
PLAT = {"KR": "kr", "JP": "jp1", "EUW": "euw1", "EUNE": "eun1", "NA": "na1", "BR": "br1", "LAN": "la1", "LAS": "la2", "OCE": "oc1", "TR": "tr1", "RU": "ru",
        "VN": "vn2", "TW": "tw2", "SG": "sg2", "PH": "ph2", "TH": "th2"}
REG = {"KR": "asia", "JP": "asia", "EUW": "europe", "EUNE": "europe", "TR": "europe", "RU": "europe", "NA": "americas", "BR": "americas", "LAN": "americas", "LAS": "americas",
       "OCE": "sea", "VN": "sea", "TW": "sea", "SG": "sea", "PH": "sea", "TH": "sea"}
LEAGUE_DEFAULT = {"LCK": "KR", "LPL": "KR", "LEC": "EUW", "LCS": "NA", "CBLOL": "BR", "LCP": "KR", "LTA": "NA", "PCS": "SG", "VCS": "VN"}
TIERS = ["IRON", "BRONZE", "SILVER", "GOLD", "PLATINUM", "EMERALD", "DIAMOND", "MASTER", "GRANDMASTER", "CHALLENGER"]
DIV = {"I": 3, "II": 2, "III": 1, "IV": 0}

def parse_ids(text, default):
    """'KR: Hide on bush#KR1, EUW: Foo#EUW' -> [(region, 'Hide on bush', 'KR1'), ...]; entries without a #tag are skipped."""
    out, seen = [], set()
    for part in re.split(r"[,;\n]|<br\s*/?>", text or ""):
        part = part.strip()
        m = re.match(r"^(?:([A-Za-z]{2,4})\s*[:\-]\s*)?(.+?)#([A-Za-z0-9]{2,6})$", part)
        if not m: continue
        reg = (m.group(1) or "").upper(); reg = reg if reg in PLAT else default
        k = (reg, m.group(2).strip().lower(), m.group(3).lower())
        if k in seen: continue
        seen.add(k); out.append((reg, m.group(2).strip(), m.group(3)))
    return out

def score(e):
    """Sortable strength of a ranked entry (tier, division, LP)."""
    if not e or not e.get("tier"): return -1
    t = TIERS.index(e["tier"]) if e["tier"] in TIERS else -1
    return t * 10000 + (DIV.get(e.get("rank"), 0) * 1000 if t < 7 else 0) + e.get("lp", 0)

def load_accounts(players, region_of):
    import requests
    try: old = json.loads(ACC.read_text(encoding="utf-8"))
    except Exception: old = {}
    manual = {}
    if MANUAL.exists():
        for row in csv.reader(MANUAL.read_text(encoding="utf-8").splitlines()):
            if len(row) >= 2 and row[0].strip() and not row[0].startswith("#"): manual.setdefault(row[0].strip(), []).append(",".join(row[1:]))
    now = time.time(); out = dict(old)
    todo = [p for p in players if p not in manual and now - (old.get(p) or {}).get("ts", 0) > ACC_REFRESH_DAYS * 86400]
    print("soloQ accounts: %d players, %d typed by hand, %d to look up on Leaguepedia" % (len(players), len(manual), len(todo)))
    if todo:
        s = requests.Session(); s.headers["User-Agent"] = UA; t_end = time.time() + 150
        for i in range(0, len(todo), 20):
            if time.time() > t_end: print("  stopping the wiki lookups for this run (time)"); break
            chunk = todo[i:i + 20]; ids = ",".join("'" + n.replace("'", "\\'") + "'" for n in chunk)
            try:
                r = s.get("https://lol.fandom.com/api.php", params=dict(format="json", action="cargoquery", tables="Players", fields="ID,SoloqueueIds,IsRetired", where="ID IN (%s)" % ids, limit=500), timeout=60)
                d = r.json()
            except Exception as ex: print("  wiki request failed:", ex); break
            if (d.get("error") or {}).get("code") == "ratelimited": print("  wiki rate limit; the rest follows on the next run"); break
            by = {}
            for row in d.get("cargoquery", []):
                t = row.get("title", row)
                if str(t.get("IsRetired", "")).lower() in ("yes", "1", "true"): continue
                by.setdefault((t.get("ID") or "").lower(), []).append(t.get("SoloqueueIds") or "")
            for n in chunk: out[n] = dict(raw=" , ".join(by.get(n.lower(), [])), ts=now)
            time.sleep(20)
    res = {}
    for p in players:
        raw = ",".join(manual[p]) if p in manual else (out.get(p) or {}).get("raw", "")
        res[p] = parse_ids(raw, region_of.get(p, "KR"))
    ACC.parent.mkdir(exist_ok=True); ACC.write_text(json.dumps(out, ensure_ascii=False))
    print("  accounts with a #tag: %d for %d of %d players" % (sum(len(v) for v in res.values()), sum(1 for v in res.values() if v), len(players)))
    return res

class Riot:
    def __init__(self):
        import requests
        self.s = requests.Session(); self.s.headers.update({"X-Riot-Token": KEY, "User-Agent": UA}); self.last = 0; self.t_end = time.time() + BUDGET; self.calls = 0
    def out_of_time(self): return time.time() > self.t_end
    def get(self, url):
        for attempt in range(3):
            wait = GAP - (time.time() - self.last)
            if wait > 0: time.sleep(wait)
            self.last = time.time(); self.calls += 1
            r = self.s.get(url, timeout=30)
            if r.status_code == 429: time.sleep(int(r.headers.get("Retry-After", "10")) + 1); continue
            if r.status_code in (401, 403): raise PermissionError("Riot API key rejected (%d) - it may have expired" % r.status_code)
            if r.status_code == 404: return None
            r.raise_for_status(); return r.json()
        return None

def fetch_account(rt, reg, name, tag, prev):
    from urllib.parse import quote
    host = "https://%s.api.riotgames.com"
    puuid = (prev or {}).get("puuid")
    if not puuid:
        a = rt.get((host % REG[reg]) + "/riot/account/v1/accounts/by-riot-id/%s/%s" % (quote(name), quote(tag)))
        if not a: return dict(id="%s#%s" % (name, tag), reg=reg, missing=True, ts=time.time())
        puuid = a["puuid"]
    ents = rt.get((host % PLAT[reg]) + "/lol/league/v4/entries/by-puuid/" + puuid) or []
    solo = next((e for e in ents if e.get("queueType") == "RANKED_SOLO_5x5"), None)
    ids = rt.get((host % REG[reg]) + "/lol/match/v5/matches/by-puuid/%s/ids?queue=420&count=%d" % (puuid, RECENT)) or []
    known = {g["id"]: g for g in (prev or {}).get("games", [])}
    games = []
    for mid in ids:
        if mid in known: games.append(known[mid]); continue
        if rt.out_of_time(): break
        m = rt.get((host % REG[reg]) + "/lol/match/v5/matches/" + mid)
        if not m: continue
        info = m["info"]; me = next((p for p in info["participants"] if p["puuid"] == puuid), None)
        if me: games.append(dict(id=mid, ts=info.get("gameEndTimestamp") or info.get("gameCreation"), champ=me["championName"], k=me["kills"], d=me["deaths"], a=me["assists"], win=bool(me["win"]),
                                 cs=me.get("totalMinionsKilled", 0) + me.get("neutralMinionsKilled", 0), dur=info.get("gameDuration", 0)))
    games.sort(key=lambda g: g.get("ts") or 0, reverse=True)
    e = dict(id="%s#%s" % (name, tag), reg=reg, puuid=puuid, ts=time.time(), games=games[:RECENT])
    if solo: e.update(tier=solo["tier"], rank=solo.get("rank"), lp=solo.get("leaguePoints", 0), wins=solo.get("wins", 0), losses=solo.get("losses", 0))
    return e

def main():
    sys.path.insert(0, str(ROOT))
    import build
    w = build.load_event(build.CSV_DEFAULT); pl = w[w.position != "team"]
    players = sorted(set(pl.playername))
    team_of = {r.playername: r.teamname for r in pl.drop_duplicates("playername", keep="last").itertuples()}
    region_of = {p: LEAGUE_DEFAULT.get(build.REGION.get(build.CODE.get(t, ""), ""), "KR") for p, t in team_of.items()}
    accounts = load_accounts(players, region_of)
    if not KEY:
        print("no RIOT_API_KEY secret: soloQ ranks are skipped (add the secret in the repository settings to turn the Bootcamp page on)"); return
    try: data = json.loads(OUT.read_text(encoding="utf-8"))
    except Exception: data = {}
    data.setdefault("players", {})
    todo = []
    for p, accs in accounts.items():
        for reg, name, tag in accs:
            prev = next((a for a in data["players"].get(p, []) if a["id"].lower() == ("%s#%s" % (name, tag)).lower()), None)
            if (prev or {}).get("missing") and time.time() - prev["ts"] < 24 * 3600: continue
            if prev and time.time() - prev["ts"] < MIN_AGE: continue
            todo.append(((prev or {}).get("ts", 0), p, reg, name, tag, prev))
    todo.sort(key=lambda x: x[0])
    print("accounts to refresh now: %d" % len(todo))
    rt = Riot(); done = 0
    try:
        for _, p, reg, name, tag, prev in todo:
            if rt.out_of_time(): break
            try: e = fetch_account(rt, reg, name, tag, prev)
            except PermissionError: raise
            except Exception as ex: print("  %s %s#%s failed: %s" % (p, name, tag, ex)); continue
            lst = [a for a in data["players"].get(p, []) if a["id"].lower() != e["id"].lower()] + [e]
            data["players"][p] = lst; done += 1
    except PermissionError as ex: print("STOPPED:", ex)
    # drop accounts that are no longer listed
    for p in list(data["players"]):
        keep = {("%s#%s" % (n, t)).lower() for _, n, t in accounts.get(p, [])}
        data["players"][p] = [a for a in data["players"][p] if a["id"].lower() in keep]
    data["updated"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    OUT.parent.mkdir(exist_ok=True); OUT.write_text(json.dumps(data, ensure_ascii=False))
    ranked = sum(1 for v in data["players"].values() if any(a.get("tier") for a in v))
    print("bootcamp: %d accounts refreshed (%d Riot calls) | %d of %d players have a ranked account" % (done, rt.calls, ranked, len(players)))

if __name__ == "__main__":
    try: main()
    except Exception as e: print("bootcamp fetch failed (keeping what is saved):", repr(e), file=sys.stderr)
