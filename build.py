#!/usr/bin/env python3
"""Rebuild the whole LoL View Stats site from an Oracle's Elixir CSV.

    python build.py [path/to/2026_LoL_esports_match_data_from_OraclesElixir.csv]

Reads the hand-designed pages in site/ (they are templates: every data blob inside them is replaced),
writes the finished site to dist/. Nothing in site/ is modified, so the build can be re-run any time.
"""
import base64, io, json, os, re, sys
from pathlib import Path
import pandas as pd
from PIL import Image

ROOT = Path(__file__).resolve().parent
os.chdir(ROOT)
sys.path.insert(0, str(ROOT / "rating"))

# ----------------------------------------------------------------------------------------------
# SETTINGS - the only things that change between events
# ----------------------------------------------------------------------------------------------
LEAGUE = "WLDs"                 # Oracle's Elixir league tag of the event shown on the site
MAIN_START = "2026-10-23"       # first day of the main stage (earlier Worlds rows are play-ins/qualifier)
TZ = "Europe/London"            # all times on the site are shown in this timezone
CSV_DEFAULT = ROOT / "data" / "2026_LoL_esports_match_data_from_OraclesElixir.csv"

NAME_FIX = {"Team Liquid": "Team Liquid Alienware"}       # shown name differs from Oracle's Elixir's
CODE = {"Gen.G": "GEN", "Invictus Gaming": "IG", "Hanwha Life Esports": "HLE", "Top Esports": "TES", "Movistar KOI": "MKOI",
        "Bilibili Gaming": "BLG", "Karmine Corp": "KC", "Anyone's Legend": "AL", "Dplus Kia": "DK", "G2 Esports": "G2",
        "Team Liquid": "TLAW", "Team Liquid Alienware": "TLAW", "CTBC Flying Oyster": "CFO", "LØS": "LOS", "T1": "T1", "LYON": "LYON", "Team Secret Whales": "TSW",
        # other tier 1 teams (used by the Power Rankings; codes match the logo keys on the homepage)
        "FURIA": "FUR", "Fluxo W7M": "FX", "LOUD": "LOUD", "Leviatan": "LEV", "RED Canids": "RED", "Vivo Keyd Stars": "VKS", "paiN Gaming": "PAIN",
        "BNK FEARX": "BFX", "DN SOOPers": "DNS", "HANJIN BRION": "BRO", "KT Rolster": "KT", "Kiwoom DRX": "KRX", "Nongshim RedForce": "NS",
        "Deep Cross Gaming": "DCG", "DetonatioN FocusMe": "DFM", "Fukuoka SoftBank HAWKS gaming": "SHG", "GAM Esports": "GAM", "Ground Zero Gaming": "GZ", "MVK Esports": "MVK",
        "Cloud9": "C9", "Dignitas": "DIG", "Disguised": "DSG", "FlyQuest": "FLY", "Sentinels": "SEN", "Shopify Rebellion": "SR",
        "Fnatic": "FNC", "GiantX": "GX", "Natus Vincere": "NAVI", "SK Gaming": "SK", "Shifters": "SHFT", "Team Heretics": "TH", "Team Vitality": "VIT",
        "EDward Gaming": "EDG", "JD Gaming": "JDG", "LGD Gaming": "LGD", "LNG Esports": "LNG", "Ninjas in Pyjamas": "NIP", "Oh My God": "OMG",
        "Team WE": "WE", "ThunderTalk Gaming": "TT", "Ultra Prime": "UP", "Weibo Gaming": "WBG"}
TIER1_LEAGUES = ["LCK", "LPL", "LEC", "LCS", "LCP", "CBLOL"]   # which leagues count as tier 1 for the Power Rankings
RANK_MIN_GAMES = 20          # a team needs this many games in those leagues this year to be ranked (58 teams on today's data)
RANK_CHANGE_DAYS = 7         # the up/down arrows compare with the ranking this many days ago
REGION = {"LYON": "LCS", "TSW": "LCP", "GEN": "LCK", "HLE": "LCK", "DK": "LCK", "T1": "LCK", "IG": "LPL", "TES": "LPL", "BLG": "LPL",
          "AL": "LPL", "G2": "LEC", "KC": "LEC", "MKOI": "LEC", "TLAW": "LCS", "CFO": "LCP", "LOS": "CBLOL"}
ROLE = {"top": "Top", "jng": "Jungle", "mid": "Mid", "bot": "Bot", "sup": "Support"}
ORDER = ["top", "jng", "mid", "bot", "sup"]
ICON_ALIASES = {"renataglasc": "renataglaasc", "monkeyking": "wukong"}   # OE / Riot-feed spelling -> asset file name

# ----------------------------------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------------------------------
def rd(fn): return open(fn, encoding="utf-8").read()
WHITE_LOGOS = ["DK", "G2", "GX", "KRX", "PAIN", "SHG", "SK", "SR", "TL", "TLAW", "TSW", "VKS"]   # logos drawn in white: inverted in light mode, same list on every page

def wr(fn, s):
    s = re.sub(r"var LW = \{[^}]*\}", lambda m: "var LW = " + json.dumps({k: 1 for k in WHITE_LOGOS}), s)
    Path(fn).parent.mkdir(parents=True, exist_ok=True); open(fn, "w", encoding="utf-8").write(s)

def jget(s, name, sep=" = "):
    key = "var " + name + sep; i = s.index(key) + len(key)
    return json.JSONDecoder().raw_decode(s[i:])[0]

def jreplace(s, name, new, sep=" = "):
    key = "var " + name + sep; i = s.index(key) + len(key)
    _, e = json.JSONDecoder().raw_decode(s[i:])
    return s[:i] + json.dumps(new, ensure_ascii=False) + s[i + e:]

def b64webp(im, q):
    b = io.BytesIO(); im.save(b, "WEBP", quality=q); return "data:image/webp;base64," + base64.b64encode(b.getvalue()).decode()

def need_code(name):
    if name not in CODE:
        sys.exit("Unknown team '%s' - add it to CODE and REGION at the top of build.py (and a logo to the pages)." % name)
    return CODE[name]

slug = lambda x: re.sub(r"[^a-z0-9]", "", x.lower())
CHAMP_FILES = sorted(os.listdir("assets/champions"))
PLAYER_FILES = sorted(os.listdir("assets/players"))

def champ_key(n):
    k = re.sub(r"[^a-z]", "", n.lower()); k = ICON_ALIASES.get(k, k)
    for f in CHAMP_FILES:
        if f[:-5] == k: return k
    for f in CHAMP_FILES:
        b = f[:-5]
        if b != "_empty" and (k.startswith(b) or b.startswith(k)): return b
    return None

def champ_icon(key, size, q):
    im = Image.open("assets/champions/%s.webp" % key).convert("RGBA")
    im = im.resize((size, size), Image.LANCZOS) if size == 68 else im
    if size != 68: im.thumbnail((size, size))
    return b64webp(im, q)

# ----------------------------------------------------------------------------------------------
# 1. load + rating
# ----------------------------------------------------------------------------------------------
def load_event(csv):
    df = pd.read_csv(csv, low_memory=False)
    df = df[(df.league == LEAGUE) & (df.date >= MAIN_START)].copy()
    df["teamname"] = df["teamname"].replace(NAME_FIX)
    return df

def ratings(csv):
    """Player rating (see rating/METHODOLOGY idea): Elo-adjusted role z-scores -> site scale."""
    import data as RD, rating as RR
    df = RD.load(str(csv)); teams, players = RD.split(df)
    m = RR.match_table(players, teams)
    lb = RR.aggregate(m, stage="Main stage").set_index("player")["rating"]
    return {p: round(min(99.9, max(1.0, 68 + 4 * (float(v) - 50))), 1) for p, v in lb.items()}

# ----------------------------------------------------------------------------------------------
# 2. homepage / players data (WD)
# ----------------------------------------------------------------------------------------------
def build_wd(w, rt):
    G = w.gameid.nunique(); pl = w[w.position != "team"]; team = w[w.position == "team"]
    tk = team.set_index(["gameid", "side"])["teamkills"].to_dict()
    pl = pl.assign(tkills=[tk[(g, s)] for g, s in zip(pl.gameid, pl.side)])
    rows = []
    for (name, tn, pos), g in pl.groupby(["playername", "teamname", "position"]):
        n = len(g); K = g.kills.sum(); D = g.deaths.sum(); A = g.assists.sum()
        rows.append(dict(p=name, t=need_code(tn), r=ROLE[pos], g=n, wp=float(g.result.mean() * 100), kda=float((K + A) / max(D, 1)), k=float(K / n), d=float(D / n), a=float(A / n),
                         dpm=float(g.dpm.mean()), cs=float(g.cspm.mean()), gd=float(g.golddiffat15.mean()), csd=float(g.csdiffat15.mean()), xpd=float(g.xpdiffat15.mean()),
                         ds=float(g.damageshare.mean() * 100), gpm=float(g["earned gpm"].mean()), kp=round(float((K + A) / g.tkills.sum() * 100), 1)))
    for r in rows: r["rt"] = rt.get(r["p"], 50.0)
    P = sorted(rows, key=lambda r: (-r["kda"], -r["gd"]))
    rank = lambda role, key, v: 1 + sum(1 for r in rows if r["r"] == role and r[key] > v + 1e-9)
    sg = lambda v: ("+" if v > 0 else "") + format(round(v), ",")
    top = []
    for role in ["Top", "Jungle", "Mid", "Bot", "Support"]:
        best = sorted([r for r in rows if r["r"] == role], key=lambda r: (-r["kda"], -r["gd"]))[0]
        keys = ["kda", "wp", "cs", "gd", "csd", "xpd"]
        top.append(dict(role=role, p=best["p"], t=best["t"], v=[f'{best["kda"]:.1f}', f'{best["wp"]:.1f}', f'{best["cs"]:.1f}', sg(best["gd"]), sg(best["csd"]), sg(best["xpd"])],
                        rk=[rank(role, k, best[k]) for k in keys]))
    tb = {}
    for _, r in team.iterrows():
        for b in ["ban1", "ban2", "ban3", "ban4", "ban5"]:
            if isinstance(r[b], str): tb[r[b]] = tb.get(r[b], 0) + 1

    def champ_rows(frame, with_bans_only):
        out = []
        for c in set(frame.champion) | (set(tb) if with_bans_only else set()):
            g = frame[frame.champion == c]; n = len(g); b = tb.get(c, 0)
            d = dict(c=c, pk=n, bn=b, pr=round((n + b) / G * 100), w=int(g.result.sum()) if n else 0, l=int(n - g.result.sum()) if n else 0)
            if n:
                K, D, A = g.kills.sum(), g.deaths.sum(), g.assists.sum()
                d.update(wr=round(g.result.mean() * 100), kda=round((K + A) / max(D, 1), 1), cs=round(g.cspm.mean(), 1), dpm=round(g.dpm.mean()),
                         gd=round(g.golddiffat15.mean()), csd=round(g.csdiffat15.mean()))
            for k in ("wr", "kda", "cs", "dpm", "gd", "csd"): d.setdefault(k, None)
            out.append(d)
        return out
    allc = champ_rows(pl, True); allc.sort(key=lambda d: (-d["pr"], -d["pk"], -d["w"], d["c"]))
    cbr = {}
    for role in ["Top", "Jungle", "Mid", "Bot", "Support"]:
        pos = [k for k, v in ROLE.items() if v == role][0]
        l = champ_rows(pl[pl.position == pos], False); l.sort(key=lambda d: (-d["pk"], -d["w"], -d["bn"], d["c"])); cbr[role] = l
    return dict(games=G, players=P, top=top, champs=allc[:10], cbr=cbr, champsAll=allc)

# ----------------------------------------------------------------------------------------------
# 3. Swiss standings + recent results
# ----------------------------------------------------------------------------------------------
def build_standings(w):
    t = w[w.position == "team"].copy(); t["code"] = t.teamname.map(need_code)
    o = t.set_index(["gameid", "side"])["code"].to_dict(); t["opp"] = [o[(g, "Red" if s == "Blue" else "Blue")] for g, s in zip(t.gameid, t.side)]
    t = t.sort_values("date"); out = {}
    for c, g in t.groupby("code"):
        series = []
        for r in g.itertuples():
            if series and series[-1]["opp"] == r.opp: series[-1]["gw" if r.result else "gl"] += 1
            else: series.append(dict(opp=r.opp, gw=int(r.result), gl=int(not r.result)))
        w_ = l_ = 0
        for s in series:
            bo3 = (w_, l_) in ((2, 0), (0, 2))
            done = (s["gw"] + s["gl"] == 1 and not bo3) or max(s["gw"], s["gl"]) >= 2
            s["bo3"] = bo3 or s["gw"] + s["gl"] > 1
            s["res"] = ("W" if s["gw"] > s["gl"] else "L") if done else "…"
            if s["res"] == "W": w_ += 1
            elif s["res"] == "L": l_ += 1
        out[c] = dict(w=w_, l=l_, rounds=[dict(res=s["res"], opp=s["opp"], sc=(f'{s["gw"]}-{s["gl"]}' if s["bo3"] else "")) for s in series])
    return out

def build_recent(w, extra=()):
    """One entry per series: games between the same two teams less than 12 hours apart belong to the same series
    (so a best-of-3 that runs past midnight is still one series)."""
    tm = w[w.position == "team"].copy(); tm["code"] = tm.teamname.map(need_code)
    games = []
    for gid, g in tm.groupby("gameid"):
        b = g[g.side == "Blue"].iloc[0]; r = g[g.side == "Red"].iloc[0]
        games.append((pd.Timestamp(b.date), frozenset([b.code, r.code]), b, r, gid))
    games += list(extra)
    games.sort(key=lambda x: x[0])
    ser = []          # each: dict(pair, games)
    for g in games:
        for s_ in reversed(ser):
            if s_["pair"] == g[1]:
                if g[0] - s_["games"][-1][0] < pd.Timedelta(hours=12): s_["games"].append(g); break
                ser.append(dict(pair=g[1], games=[g])); break
        else: ser.append(dict(pair=g[1], games=[g]))
    out = []
    try: sched = json.loads((ROOT / "data" / "schedule.json").read_text(encoding="utf-8"))["matches"]
    except Exception: sched = []
    for s_ in ser:
        gl = s_["games"]; wins = {}
        for _, _p, b, r, _g in gl:
            wc = b.code if b.result else r.code; wins[wc] = wins.get(wc, 0) + 1
        # a series that is still being played (e.g. 1:1 in a best-of-3) does not belong in Recent Results
        bo = 0; t_first = gl[0][0].tz_localize("UTC") if gl[0][0].tzinfo is None else gl[0][0]
        for m in sched:
            if frozenset([m["home"], m["away"]]) == s_["pair"] and abs((pd.Timestamp(m["start"]) - t_first).total_seconds()) < 12 * 3600: bo = int(m.get("bo") or 0); break
        need = bo // 2 + 1 if bo else (2 if len(gl) >= 2 else 1)
        if max(wins.values()) < need: continue
        ws = max(wins, key=wins.get); ls = [c for c in s_["pair"] if c != ws][0]
        lastg = gl[-1]; d = lastg[0].tz_localize("UTC").tz_convert(TZ)
        out.append((lastg[0], [ws, "%d:%d" % (wins[ws], wins.get(ls, 0)), ls, d.strftime("%H:%M"), d.strftime("%b %-d"), gl[0][4], int(lastg[0].tz_localize("UTC").timestamp() * 1000)]))
    out.sort(key=lambda x: x[0], reverse=True)
    return [x[1] for x in out[:200]]

# ----------------------------------------------------------------------------------------------
# 4. game / player / team / champion page data
# ----------------------------------------------------------------------------------------------
def load_riot_games():
    try: return json.loads((ROOT / "data" / "riot_games.json").read_text(encoding="utf-8"))
    except Exception: return {}

def riot_only_games(w, ic):
    """Finished games that Riot's feed (data/riot_games.json, written by fetch_riot_games.py) has but Oracle's Elixir does not yet,
    in the same shape as the other game-page entries. Damage is only a share of the team total here, so they are flagged pct."""
    RG = load_riot_games(); out = []
    if not RG: return out
    oe = []
    for gid, g in w[w.position == "team"].groupby("gameid"):
        b = g[g.side == "Blue"].iloc[0]; r = g[g.side == "Red"].iloc[0]
        oe.append((sorted([CODE.get(b.teamname, ""), CODE.get(r.teamname, "")]), int(b.game), pd.Timestamp(b.date)))
    for rid, r in RG.items():
        codes = sorted(t["code"] for t in r["teams"]); n = int(r["number"]); t0 = pd.Timestamp(r["start"]).tz_convert("UTC").tz_localize(None)
        if any(c == codes and k == n and abs((d - t0).total_seconds()) < 12 * 3600 for c, k, d in oe): continue
        teams, ok = [], True
        for ti, t in enumerate(r["teams"]):
            by = {p_["pos"]: p_ for p_ in t["players"]}; players = []
            for pos in ORDER:
                p_ = by.get(pos)
                if not p_: ok = False; break
                players.append(dict(role=ROLE[pos], name=p_["name"], champ=p_["champ"], ic=ic(p_["champ"]), k=p_["k"], d=p_["d"], a=p_["a"], dmg=p_["share"], cs=p_["cs"], gold=p_["gold"],
                                    it=tidy_items(p_["items"]), rn=([p_["perks"][0], p_["sub"]] if p_.get("perks") and p_.get("sub") else None)))
            if not ok: break
            dr = {}
            for x in t["dragons"]: dr[x] = dr.get(x, 0) + 1
            teams.append(dict(code=t["code"], name=t["name"], side=t["side"].capitalize(), win=int(r["blue_win"] if ti == 0 else not r["blue_win"]), k=sum(q["k"] for q in players), d=sum(q["d"] for q in players),
                              a=sum(q["a"] for q in players), gold=t["gold"], towers=t["towers"], grubs=0, heralds=0, elders=dr.get("elder", 0), barons=t["barons"],
                              drakes=[(k_, dr.get(k_, 0)) for k_ in ("infernal", "mountain", "cloud", "ocean", "chemtech", "hextech")], bans=[], players=players))
        if not ok or len(teams) != 2: print("  skipped incomplete Riot game", rid); continue
        RIOT_MAP[rid] = rid
        out.append(dict(id=rid, pct=1, bo=r.get("bo") or 0, patch=(".".join(str(r["patch"]).split(".")[:2]) if r.get("patch") else None),
                        date=t0.tz_localize("UTC").tz_convert(TZ).strftime("%b %-d"), start=str(t0), len=r["len"], teams=teams, gold=r["gold"]))
    if out: print("  games from Riot's feed (not in Oracle's Elixir yet):", len(out))
    return out

def build_game(w, logos_all):
    icons = {}
    def ic(n):
        k = champ_key(n)
        if not k: print("  no champion icon for", n); return None
        if k not in icons: icons[k] = champ_icon(k, 72, 82)
        return k
    games = []
    for gid, g in w.groupby("gameid"):
        t = g[g.position == "team"].set_index("side"); p = g[g.position != "team"]; gl = int(t.iloc[0].gamelength); teams = []
        for side in ["Blue", "Red"]:
            tr = t.loc[side]; pl = p[p.side == side]; players = []
            for pos in ORDER:
                r = pl[pl.position == pos].iloc[0]
                players.append(dict(role=ROLE[pos], name=r.playername, champ=r.champion, ic=ic(r.champion), k=int(r.kills), d=int(r.deaths), a=int(r.assists),
                                    dmg=int(r.damagetochampions), cs=int(r["total cs"]), gold=int(r.totalgold)))
            d = lambda c: int(tr[c]) if pd.notna(tr[c]) else 0
            teams.append(dict(code=need_code(tr.teamname), name=tr.teamname, side=side, win=int(tr.result), k=int(pl.kills.sum()), d=int(pl.deaths.sum()), a=int(pl.assists.sum()),
                              gold=int(tr.totalgold), towers=d("towers"), inh=d("inhibitors"), fb=d("firstblood"), ft=d("firsttower"), grubs=d("void_grubs"), heralds=d("heralds"), elders=d("elders"), barons=d("barons"),
                              drakes=[("infernal", d("infernals")), ("mountain", d("mountains")), ("cloud", d("clouds")), ("ocean", d("oceans")), ("chemtech", d("chemtechs")), ("hextech", d("hextechs"))],
                              bans=[dict(c=b, ic=ic(b)) for b in [tr[f"ban{i}"] for i in range(1, 6)] if isinstance(b, str)], players=players))
        series = [[0, 0]]
        for m in (10, 15, 20, 25):
            b = g[(g.side == "Blue") & (g.position != "team")][f"goldat{m}"]; r = g[(g.side == "Red") & (g.position != "team")][f"goldat{m}"]
            if b.notna().all() and len(b) == 5 and gl > m * 60 + 30: series.append([m, int(b.sum() - r.sum())])
        series.append([round(gl / 60, 1), teams[0]["gold"] - teams[1]["gold"]])
        games.append(dict(id=gid, patch=("%.2f" % float(g.patch.iloc[0]) if "patch" in g and pd.notna(g.patch.iloc[0]) else None), date=pd.Timestamp(g.date.iloc[0]).tz_localize("UTC").tz_convert(TZ).strftime("%b %-d"), start=str(g.date.iloc[0]), len=gl, teams=teams, gold=series))
    games += riot_only_games(w, ic)
    games.sort(key=lambda x: x["start"])
    for i, g in enumerate(games): g["n"] = i + 1
    # series = same two teams, less than 12 h apart; best-of is read from the Riot schedule when cached, else inferred
    cache = {}
    try: cache = json.loads((ROOT / "data" / "items_cache.json").read_text(encoding="utf-8"))
    except Exception: pass
    for g in games:
        if g.get("pct") and g.get("bo"): cache.setdefault(g["id"], {}).setdefault("bo", g["bo"])
    sers = []
    for g in games:
        pair = frozenset(t["code"] for t in g["teams"]); t0 = pd.Timestamp(g["start"])
        for s_ in reversed(sers):
            if s_["pair"] == pair:
                if t0 - s_["last"] < pd.Timedelta(hours=12): s_["g"].append(g); s_["last"] = t0; break
                sers.append(dict(pair=pair, g=[g], last=t0)); break
        else: sers.append(dict(pair=pair, g=[g], last=t0))
    for k, s_ in enumerate(sers):
        wins = {}
        for g in s_["g"]:
            wc = next(t["code"] for t in g["teams"] if t["win"]); wins[wc] = wins.get(wc, 0) + 1
        n = len(s_["g"]); mx = max(wins.values())
        bo = 5 if (mx >= 3 or n >= 4) else 3 if (n >= 2 or mx >= 2) else 1
        for g in s_["g"]:
            rec = cache.get(g["id"]) or {}
            if rec.get("bo"): bo = int(rec["bo"]); break
        for g in s_["g"]: g["sid"] = k; g["bo"] = bo
    used = {t["code"] for g in games for t in g["teams"]}
    return dict(games=games, icons=icons, tournament="Worlds 2026", logos={k: logos_all[k] for k in used if k in logos_all})

def build_profiles(w, faces_fallback, logos_all):
    p = w[w.position != "team"].copy(); t = w[w.position == "team"]
    tk = t.set_index(["gameid", "side"])["teamkills"].to_dict(); tn = t.set_index(["gameid", "side"])["teamname"].to_dict()
    icons = {}
    def ic(n):
        k = champ_key(n)
        if k and k not in icons: icons[k] = champ_icon(k, 64, 80)
        return k
    def face(name, tc):
        c = [f for f in PLAYER_FILES if f[:-5] == tc.lower() + "-" + slug(name)]
        if c:
            im = Image.open("assets/players/" + c[0]).convert("RGBA"); im.thumbnail((240, 240)); return b64webp(im, 80)
        print("  no portrait for", name, tc); return faces_fallback.get(name)
    rows = []
    for _, r in p.iterrows():
        team = need_code(r.teamname); opp = need_code(tn[(r.gameid, "Red" if r.side == "Blue" else "Blue")])
        rows.append(dict(player=r.playername, team=team, opp=opp, role=ROLE[r.position], champ=r.champion, ic=ic(r.champion), win=int(r.result), k=int(r.kills), d=int(r.deaths), a=int(r.assists),
                         cs=float(r["total cs"]), gl=r.gamelength / 60, dmg=float(r.damagetochampions), gold=float(r.totalgold), tk=float(tk[(r.gameid, r.side)]), ds=float(r.damageshare), gs=float(r.earnedgoldshare),
                         csd=float(r.csdiffat15) if pd.notna(r.csdiffat15) else None, gd=float(r.golddiffat15) if pd.notna(r.golddiffat15) else None, xpd=float(r.xpdiffat15) if pd.notna(r.xpdiffat15) else None,
                         vs=float(r.vspm), wpm=float(r.wpm), wcpm=float(r.wcpm), dtm=float(r.damagetakenperminute), date=str(r.date)[:10], gid=r.gameid, side=r.side, pt=("%.2f" % float(r.patch) if "patch" in r.index and pd.notna(r.patch) else None)))
    res = {}
    for pl in sorted(set(x["player"] for x in rows)):
        g = [x for x in rows if x["player"] == pl]
        res[pl] = dict(name=pl, team=g[0]["team"], role=g[0]["role"], region=REGION.get(g[0]["team"]), games=g)
    for pl, v in res.items(): v["face"] = face(pl, v["team"])
    used = {v["team"] for v in res.values()} | {x["opp"] for v in res.values() for x in v["games"]}
    return dict(players=res, icons=icons, logos={k: logos_all[k] for k in used if k in logos_all})

def team_season(g):
    """Season averages of a team for the live page's team comparison: [games, win%, GD@15, kills, deaths, towers, drakes, barons, grubs, heralds, first blood %, first tower %, minutes]."""
    n = len(g) or 1; av = lambda k: sum(x[k] for x in g) / n
    return [len(g), round(100 * sum(x["win"] for x in g) / n, 1), round(av("gd")), round(av("k"), 1), round(av("d"), 1), round(av("tw"), 1), round(av("dr"), 1), round(av("ba"), 2),
            round(av("gr"), 1), round(av("he"), 1), round(100 * av("fb")), round(100 * av("ft")), round(av("gl") / 60, 1)]

def build_teams(w, P):
    out = {}
    for gid, g in w.groupby("gameid"):
        for side in ["Blue", "Red"]:
            t = g[(g.side == side) & (g.position == "team")].iloc[0]; pl = g[(g.side == side) & (g.position != "team")]
            c = need_code(t.teamname); oth = "Red" if side == "Blue" else "Blue"; o = need_code(g[(g.side == oth) & (g.position == "team")].iloc[0].teamname)
            num = lambda col: float(t[col]) if pd.notna(t[col]) else 0.0
            row = dict(gid=gid, opp=o, win=int(t.result), gl=float(t.gamelength), date=str(t.date)[:10], k=float(pl.kills.sum()), d=float(pl.deaths.sum()), a=float(pl.assists.sum()),
                       fb=num("firstblood"), ft=num("firsttower"), dr=num("dragons"), ba=num("barons"), tw=num("towers"), gr=num("void_grubs"), he=num("heralds"),
                       gold=float(t.totalgold), dmg=float(pl.damagetochampions.sum()), vs=float(pl.vspm.mean() * 5), cs=float(pl["total cs"].sum()),
                       gd=float(pl.golddiffat15.sum()), csd=float(pl.csdiffat15.sum()), xpd=float(pl.xpdiffat15.sum()))
            out.setdefault(c, dict(code=c, name=t.teamname, region=REGION.get(c), games=[]))["games"].append(row)
    for c, v in out.items(): v["players"] = [n for n, p in P["players"].items() if p["team"] == c]
    players = {n: dict(name=n, team=p["team"], role=p["role"], face=p["face"], games=p["games"]) for n, p in P["players"].items()}
    return dict(teams=out, players=players, logos=P["logos"])

def build_g20(w):
    g20 = {}
    for r in w[w.position == "team"].itertuples():
        if pd.notna(r.golddiffat20): g20.setdefault(r.gameid, {})[need_code(r.teamname)] = int(r.golddiffat20)
    return g20

def build_champions(w, GD):
    pl = w[w.position != "team"]; tm = w[w.position == "team"]
    icons = {}
    def ic(n):
        k = champ_key(n)
        if not k: print("  no champion icon for", n); return None
        if k not in icons: icons[k] = GD["icons"].get(k) or champ_icon(k, 72, 82)
        return k
    tk = {(r.gameid, r.side): r.kills for r in tm.itertuples()}
    order = sorted(w.gameid.unique(), key=lambda x: w[w.gameid == x].date.iloc[0])
    gp = {gid: [need_code(x) for x in w[(w.gameid == gid) & (w.position == "team")].sort_values("side").teamname] for gid in order}
    f = lambda x: None if pd.isna(x) else round(float(x), 3)
    ch = {}
    for r in pl.itertuples():
        opp = pl[(pl.gameid == r.gameid) & (pl.position == r.position) & (pl.side != r.side)].iloc[0]; tkills = tk[(r.gameid, r.side)]
        row = dict(role=ROLE[r.position], player=r.playername, team=need_code(r.teamname), opp=need_code(opp.teamname), win=int(r.result), k=int(r.kills), d=int(r.deaths), a=int(r.assists),
                   cspm=f(r.cspm), dmg=f(r.damageshare), gold=f(r.earnedgoldshare), gd=f(r.golddiffat15), csd=f(r.csdiffat15), xpd=f(r.xpdiffat15),
                   kp=round((r.kills + r.assists) / tkills, 4) if tkills else None, oc=opp.champion, oi=ic(opp.champion), op=opp.playername, game=r.gameid, side=r.side, len=int(r.gamelength), date=r.date[:10], pt=("%.2f" % r.patch) if pd.notna(r.patch) else None)
        ch.setdefault(r.champion, dict(rows=[], bans=[]))["rows"].append(row)
    for r in tm.itertuples():
        bl, rd_ = gp[r.gameid]; me = need_code(r.teamname); opp = rd_ if me == bl else bl
        for n in range(1, 6):
            b = getattr(r, "ban%d" % n)
            if isinstance(b, str): ch.setdefault(b, dict(rows=[], bans=[]))["bans"].append(dict(by=me, vs=opp, ph=1 if n <= 3 else 2, game=r.gameid, win=int(r.result)))
    avg = {}
    for role, x in pl.groupby("position"):
        tot = lambda c: float(x[c].sum())
        avg[ROLE[role]] = dict(kda=(tot("kills") + tot("assists")) / max(1, tot("deaths")), cspm=float(x.cspm.mean()), dmg=float(x.damageshare.mean()), gold=float(x.earnedgoldshare.mean()),
                               kp=float(((x.kills + x.assists) / x.apply(lambda r: tk[(r.gameid, r.side)], axis=1)).mean()), gd=float(x.golddiffat15.mean()), csd=float(x.csdiffat15.mean()), xpd=float(x.xpdiffat15.mean()))
    return dict(champs={n: dict(ic=ic(n), **v) for n, v in ch.items()}, avg=avg, icons=icons, games=len(order), logos=GD["logos"])

# ----------------------------------------------------------------------------------------------
# 4d. item builds: data/items_cache.json (fetch_items.py, Riot live stats) + item icons from Data Dragon
# ----------------------------------------------------------------------------------------------
POS_OF_ROLE = {v: k for k, v in ROLE.items()}      # "Top" -> "top"

RIOT_MAP = {}   # Riot game id -> Oracle's Elixir game id, so the live page can hand finished games over to the post game page

def map_items(w):
    """(oe gameid, side, position) -> list of item ids, by matching teams + game number + start time to the Riot games."""
    try: cache = json.loads((ROOT / "data" / "items_cache.json").read_text(encoding="utf-8"))
    except Exception: print("  no item cache - item builds are skipped"); return {}
    recs = list(cache.values()); out = {}; matched = 0; total = 0; champ_bad = 0
    ALIAS = {"monkeyking": "wukong", "renata": "renataglasc", "nunu": "nunuwillump"}
    def norm(s):
        n = re.sub(r"[^a-z]", "", str(s).lower()); return ALIAS.get(n, n)
    for gid, g in w[w.position == "team"].groupby("gameid"):
        total += 1
        blue = g[g.side == "Blue"].iloc[0]; red = g[g.side == "Red"].iloc[0]
        codes = sorted([CODE.get(blue.teamname, ""), CODE.get(red.teamname, "")])
        t0 = pd.Timestamp(blue.date).tz_localize("UTC")
        cand = [r for r in recs if r["codes"] == codes and int(r["number"]) == int(blue.game) and abs((pd.Timestamp(r["start"]) - t0).total_seconds()) < 12 * 3600]
        if not cand:      # team codes can differ between Riot and Oracle's Elixir: fall back to game number, start time and the ten champions
            mine = {norm(c) for c in w[(w.gameid == gid) & (w.position != "team")].champion}
            cand = [r for r in recs if int(r["number"]) == int(blue.game) and abs((pd.Timestamp(r["start"]) - t0).total_seconds()) < 3 * 3600
                    and len(mine & {norm(p["champ"]) for p in r["players"].values()}) >= 9]
            if cand: print("  matched by champions:", gid, codes, "riot codes", cand[0]["codes"])
        if not cand: print("  no Riot data for", gid, codes, "game", int(blue.game), str(blue.date)); continue
        r = cand[0]; matched += 1; RIOT_MAP[r["id"]] = gid
        for _, p in w[(w.gameid == gid) & (w.position != "team")].iterrows():
            rp = r["players"].get(p.side.lower() + ":" + p.position)
            if not rp: continue
            if norm(rp["champ"]) != norm(p.champion) and norm(rp["champ"]) not in norm(p.champion) and norm(p.champion) not in norm(rp["champ"]): champ_bad += 1; print("  champion differs:", gid, p.side, p.position, "riot=" + str(rp["champ"]), "oe=" + str(p.champion))
            rn = rp.get("runes") or {}; pk = rn.get("perks") or []
            out[(gid, p.side, p.position)] = (rp["items"] + ([rp["tr0"]] if rp.get("tr0") and not any(i in TRINKETS for i in rp["items"]) else []), [pk[0], rn.get("sub")] if pk and rn.get("sub") else None, pk, rp.get("order") or [])
    print("  items: %d of %d games matched to Riot data%s" % (matched, total, ("; %d champion name differences (check aliases)" % champ_bad) if champ_bad else ""))
    return out

def item_assets(ids):
    """{item id: [name, icon data-uri, is_trinket, is_completed]} from Data Dragon; cached in data/item_icons.json. Empty on failure."""
    import requests
    path = ROOT / "data" / "item_icons.json"
    try: cache = json.loads(path.read_text(encoding="utf-8"))
    except Exception: cache = {}
    need = [str(i) for i in sorted(set(ids)) if str(i) not in cache or len(cache[str(i)]) < 4]
    if need:
        try:
            vers = requests.get("https://ddragon.leagueoflegends.com/api/versions.json", timeout=30).json()
            items = requests.get("https://ddragon.leagueoflegends.com/cdn/%s/data/en_US/item.json" % vers[0], timeout=60).json()["data"]
            for i in need:
                meta = items.get(i) or {}; tags = meta.get("tags") or []; gold = meta.get("gold") or {}
                tr = int("Trinket" in tags or int(i) in TRINKETS)
                cm = int(bool(gold.get("purchasable")) and not meta.get("into") and (gold.get("total") or 0) >= 2000 and not ({"Boots", "Consumable", "Trinket", "Lane", "Jungle"} & set(tags)))
                if i in cache: cache[i] = list(cache[i][:2]) + [tr, cm]; continue
                try:
                    r = requests.get("https://ddragon.leagueoflegends.com/cdn/%s/img/item/%s.png" % (vers[0], i), timeout=30); r.raise_for_status()
                    im = Image.open(io.BytesIO(r.content)).convert("RGBA"); im.thumbnail((36, 36))
                    cache[i] = [meta.get("name", "Item " + i), b64webp(im, 78), tr, cm]
                except Exception as ex: print("  no icon for item", i, "(%s)" % ex)
            path.parent.mkdir(exist_ok=True); path.write_text(json.dumps(cache, ensure_ascii=False))
        except Exception as ex: print("  item icons unavailable:", ex)
    return {i: cache[i] for i in map(str, set(ids)) if i in cache}

TRINKETS = {3330, 3340, 3363, 3364}
SUPPORT_ITEMS = {3850, 3851, 3853, 3854, 3855, 3857, 3858, 3859, 3860, 3862, 3863, 3864, 3865, 3866, 3867, 3869, 3870, 3871, 3876, 3877}   # support quest items and their upgrades
def tidy_items(it, trset=TRINKETS):
    """7 entries: up to 6 distinct items in the player's own slot order (0 = empty), then the trinket (0 = none). A support item (if held) is added as an 8th entry instead of pushing out a regular item."""
    seen, main, tr, sup = set(), [], [], []
    for i in it:
        if i in seen: continue
        seen.add(i); (tr if i in trset else sup if i in SUPPORT_ITEMS else main).append(i)
    if sup and len(main) < 6 and False: pass
    main = main[:6]
    return main + [0] * (6 - len(main)) + [tr[0] if tr else 0] + ([sup[-1]] if sup else [])

def rune_assets(pairs):
    """{id: [name, icon data-uri]} for keystones and secondary trees from Data Dragon; cached in data/rune_icons.json."""
    import requests
    path = ROOT / "data" / "rune_icons.json"
    try: cache = json.loads(path.read_text(encoding="utf-8"))
    except Exception: cache = {}
    need = {str(i) for pr in pairs for i in pr if i and str(i) not in cache}
    if need:
        try:
            ver = requests.get("https://ddragon.leagueoflegends.com/api/versions.json", timeout=30).json()[0]
            styles = requests.get("https://ddragon.leagueoflegends.com/cdn/%s/data/en_US/runesReforged.json" % ver, timeout=60).json()
            ent = {"5001": ("Health Scaling", "perk-images/StatMods/StatModsHealthScalingIcon.png"), "5002": ("Armor", "perk-images/StatMods/StatModsArmorIcon.png"),
                   "5003": ("Magic Resist", "perk-images/StatMods/StatModsMagicResIcon.png"), "5005": ("Attack Speed", "perk-images/StatMods/StatModsAttackSpeedIcon.png"),
                   "5007": ("Ability Haste", "perk-images/StatMods/StatModsCDRScalingIcon.png"), "5008": ("Adaptive Force", "perk-images/StatMods/StatModsAdaptiveForceIcon.png"),
                   "5010": ("Move Speed", "perk-images/StatMods/StatModsMovementSpeedIcon.png"), "5011": ("Health", "perk-images/StatMods/StatModsHealthPlusIcon.png"),
                   "5013": ("Tenacity", "perk-images/StatMods/StatModsTenacityIcon.png")}
            for s in styles:
                ent[str(s["id"])] = (s["name"], s["icon"])
                for sl in s["slots"]:
                    for r in sl["runes"]: ent[str(r["id"])] = (r["name"], r["icon"])
            for i in need:
                try:
                    nm, ic = ent[i]
                    r = requests.get("https://ddragon.leagueoflegends.com/cdn/img/" + ic, timeout=30); r.raise_for_status()
                    im = Image.open(io.BytesIO(r.content)).convert("RGBA"); im.thumbnail((40, 40)); cache[i] = [nm, b64webp(im, 80)]
                except Exception as e: print("  no icon for rune", i, "(%s)" % e)
            path.parent.mkdir(exist_ok=True); path.write_text(json.dumps(cache, ensure_ascii=False))
        except Exception as e: print("  rune icons unavailable:", e)
    return cache

def attach_items(w, GD, PD, CD):
    M = map_items(w)
    ro = [p for g in GD["games"] if g.get("pct") for t in g["teams"] for p in t["players"]]
    if not M and not ro: return
    raw = {k: v[0] for k, v in M.items()}
    sup_ = [(k, v[0]) for k, v in M.items() if k[2] == "sup" or str(k[2]).lower().startswith("sup")]
    print("  support players (raw item ids from Riot):", len(sup_))
    for k, v in sup_[:8]: print("    ", k, v, "| held back by tidy_items:", [i for i in v if i in SUPPORT_ITEMS])
    print("  position keys seen:", sorted({str(k[2]) for k in M})[:8])
    icons = item_assets({i for v in raw.values() for i in v} | {i for v in M.values() for i in v[3]} | {i for p in ro for i in p["it"] if i})
    trset = TRINKETS | {int(i) for i, x in icons.items() if len(x) > 2 and x[2]}
    IT = {k: tidy_items(v, trset) for k, v in raw.items()}
    RN = {k: v[1] for k, v in M.items() if v[1]}
    def fix_shards(pk):
        """Riot's feed lists a repeated stat shard only once (two adaptive force shards come as one), so such pages have 8 ids instead of 9. Put the repeat back."""
        if len(pk) != 8: return pk
        sh = pk[6:]
        a_, b_ = sh
        off, flex, dfn = {5008, 5005, 5007}, {5008, 5010, 5001}, {5011, 5013, 5001}
        if a_ in off & flex and b_ in dfn: return pk[:6] + [a_, a_, b_]       # same shard in the offence and flex slots (almost always adaptive force)
        if a_ in off and b_ in flex & dfn: return pk[:6] + [a_, b_, b_]       # same shard in the flex and defence slots
        return pk
    PK = {k: fix_shards(list(v[2])) for k, v in M.items() if v[2]}
    def completed(order):
        out = []
        for i in order:
            x = icons.get(str(i))
            if x and len(x) > 3 and x[3] and i not in out: out.append(i)
        return out[:6]
    BO = {k: completed(v[3]) for k, v in M.items()}
    for g in GD["games"]:
        for t in g["teams"]:
            for p in t["players"]:
                k = (g["id"], t["side"], POS_OF_ROLE[p["role"]]); p["it"] = IT.get(k) or p.get("it"); p["rn"] = RN.get(k) or p.get("rn")
    for pl in PD["players"].values():
        for r in pl["games"]:
            k = (r["gid"], r["side"], POS_OF_ROLE[r["role"]]); r["it"] = IT.get(k); r["rn"] = RN.get(k)
    for c in CD["champs"].values():
        for r in c["rows"]:
            k = (r["game"], r["side"], POS_OF_ROLE[r["role"]]); r["it"] = IT.get(k); r["rn"] = RN.get(k); r["pk"] = PK.get(k); r["bo"] = BO.get(k)
    runes = rune_assets(list(RN.values()) + list(PK.values()) + [p["rn"] for p in ro if p.get("rn")])
    from collections import Counter as _C
    print("  rune pages by length:", dict(_C(len(v) for v in PK.values())), "| shard sets:", dict(_C(tuple(v[6:]) for v in PK.values()).most_common(8)), "| shard ids without an icon:", sorted({i for v in PK.values() for i in v[6:] if str(i) not in runes}))
    miss = sorted({i for v in raw.values() for i in v if str(i) not in icons}); notr = sum(1 for v in IT.values() if not v[6])
    if miss: print("  items without an icon:", miss)
    print("  players without a trinket: %d of %d | with a build order: %d" % (notr, len(IT), sum(1 for v in BO.values() if v)))
    def used(rows): return {str(i) for r in rows for i in (r.get("it") or []) + (r.get("bo") or []) if i}
    def usedr(rows): return {str(i) for r in rows for i in (r.get("rn") or []) + (r.get("pk") or []) if i}
    gp = [p for g in GD["games"] for t in g["teams"] for p in t["players"]]
    pr = [r for pl in PD["players"].values() for r in pl["games"]]; cr = [r for c in CD["champs"].values() for r in c["rows"]]
    for D_, rows in ((GD, gp), (PD, pr), (CD, cr)):
        D_["items"] = {i: icons[i] for i in used(rows) if i in icons}
        D_["runes"] = {i: runes[i] for i in usedr(rows) if i in runes}
    print("  item icons embedded:", len(GD["items"]), "| rune icons:", len(GD["runes"]), "(game page)")

# ----------------------------------------------------------------------------------------------
# 4c. Power Rankings: team Elo over all 2026 games, for tier 1 teams
# ----------------------------------------------------------------------------------------------
WORLDS_RANK_FROM = MAIN_START   # the Power Rankings use only Worlds 2026 main stage games (no Play-Ins, domestic or other international results)

def build_rankings(csv):
    """Elo ranking of the teams at Worlds 2026, from main stage games only (everyone starts level at 1500)."""
    import data as RD, elo as RE, config as RC
    df = RD.load(str(csv)); teams, _ = RD.split(df)
    ww = teams[(teams.league == LEAGUE) & (teams.date >= pd.Timestamp(WORLDS_RANK_FROM))]
    keep = sorted(ww[ww.date >= pd.Timestamp(MAIN_START)].teamname.unique())          # the teams in the main stage
    _, now_r = RE.run(ww, RC.ELO_K, "flat")
    cut = ww.date.max() - pd.Timedelta(days=RANK_CHANGE_DAYS)
    old = ww[ww.date < cut]; played = set(old.teamname)
    old_r = RE.run(old, RC.ELO_K, "flat")[1] if len(old) else {}
    order = lambda r, names: {t: i + 1 for i, t in enumerate(sorted([x for x in names if x in r], key=lambda x: -r[x]))}
    rn = order(now_r, [t for t in keep if t in played] if played else keep); ro = order(old_r, [t for t in keep if t in played])
    rows = []
    for t in sorted(keep, key=lambda x: -now_r[x]):
        d = (ro[t] - rn[t]) if (t in ro and t in rn) else 0                           # arrows only for teams that already had a game a week ago
        code = CODE.get(t)
        if not code: code = re.sub(r"[^A-Z0-9]", "", "".join(w[0] for w in t.split()).upper())[:4]; print("  no code for", t, "- using", code)
        rows.append([NAME_FIX.get(t, t), REGION.get(code, ""), code, ("up%d" % d if d > 0 else "dn%d" % -d if d < 0 else ""), int(round(now_r[t]))])
    upd = pd.Timestamp(teams.date.max()).tz_localize("UTC").tz_convert(TZ).strftime("%-m/%-d/%y")
    print("  rankings: %d teams, top 3: %s" % (len(rows), ", ".join(r[2] for r in rows[:3])))
    return rows, upd, pd.Timestamp(teams.date.max()).tz_localize("UTC").strftime("%Y-%m-%dT%H:%M:%SZ")

# ----------------------------------------------------------------------------------------------
# 4a. player age / contract (auto: config/player_info_auto.json from fetch_player_info.py; manual: config/player_info.csv wins)
# ----------------------------------------------------------------------------------------------
def month_year(v):
    m = re.match(r"(\d{4})-(\d{2})", str(v or ""))
    return ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"][int(m.group(2)) - 1] + " " + m.group(1) if m else (str(v).strip() or None)

def load_player_info():
    info = {}
    try: info = json.loads((ROOT / "config" / "player_info_auto.json").read_text(encoding="utf-8"))
    except Exception: print("  no automatic player info file")
    p = ROOT / "config" / "player_info.csv"
    if p.exists():
        for r in pd.read_csv(p, dtype=str).fillna("").to_dict("records"):
            if not r.get("player"): continue
            cur = info.setdefault(r["player"], {})
            if r.get("birthdate"): cur["bd"] = r["birthdate"].strip()
            if r.get("contract"): cur["contract"] = month_year(r["contract"])
    return info

# ----------------------------------------------------------------------------------------------
# 4b. upcoming matches (from data/schedule.json, written by fetch_schedule.py)
# ----------------------------------------------------------------------------------------------
UP_KEYS = ["global", "lck", "lpl", "lec", "lcs", "cblol", "lcp"]
UP_ALIAS = {}          # schedule team code -> code used on this site, if they ever differ
PER_FILTER = 8         # rows stored per filter; the page drops started matches and shows 4

def build_upcoming(path=ROOT / "data" / "schedule.json"):
    out = {k: [] for k in UP_KEYS}
    try: raw = json.loads(Path(path).read_text(encoding="utf-8"))["matches"]
    except Exception: print("  no schedule file - Upcoming Matches will show an empty state"); return out
    now = pd.Timestamp.now(tz="UTC")
    for m in sorted(raw, key=lambda x: x["start"]):
        t0 = pd.Timestamp(m["start"])
        if t0 + pd.Timedelta(hours=3) < now: continue
        h, a = UP_ALIAS.get(m["home"], m["home"]), UP_ALIAS.get(m["away"], m["away"])
        uk = t0.tz_convert(TZ)
        row = [h, a, uk.strftime("%H:%M"), uk.strftime("%b %-d"), "BO%d" % m["bo"], m["league"], int(t0.timestamp() * 1000), m.get("mid")]
        keys = {"global"}                       # Worlds / MSI etc. appear only under Global
        if m["league"] in UP_KEYS: keys.add(m["league"])
        for k in keys:
            if len(out[k]) < PER_FILTER: out[k].append(row)
    print("  upcoming:", {k: len(v) for k, v in out.items()})
    return out

# ----------------------------------------------------------------------------------------------
# 5. write the pages
# ----------------------------------------------------------------------------------------------
def build_search(s, WD, CH):
    """Refresh the searchable teams / players / champions list; keep the static logos, flags and role icons."""
    SD = jget(s, "SD")
    names = {c: NAME_FIX.get(n, n) for c, n in SD["t"]}
    for c in {p["t"] for p in WD["players"]}: names.setdefault(c, NAME_FIX.get(next(k for k, v in CODE.items() if v == c), next(k for k, v in CODE.items() if v == c)))
    SD["t"] = [[c, names[c]] for c in names if c in {p["t"] for p in WD["players"]}] or SD["t"]
    SD["p"] = [[p["p"], p["t"], p["r"]] for p in WD["players"]]
    have = {n: i for n, i in SD["c"]}
    cs = {}
    for c in WD["champsAll"]:
        k = champ_key(c["c"])
        if k: cs[c["c"]] = have.get(c["c"]) or champ_icon(k, 36, 70)
    SD["c"] = [[n, cs[n]] for n in sorted(cs)]
    return SD

def build_bootcamp(WD, logos_all, tpl):
    """SoloQ ladder data for the Bootcamp page: data/bootcamp.json (fetch_bootcamp.py) joined with the event's players."""
    try: data = json.loads((ROOT / "data" / "bootcamp.json").read_text(encoding="utf-8"))
    except Exception: data = {}
    pl = data.get("players") or {}; players = []
    for p in WD["players"]:
        accs = [dict(id=a["id"], tier=a.get("tier"), rank=a.get("rank"), lp=a.get("lp", 0), wins=a.get("wins", 0), losses=a.get("losses", 0), missing=a.get("missing"),
                     games=[dict(champ=g["champ"], win=g["win"], k=g["k"], d=g["d"], a=g["a"], ts=g.get("ts")) for g in a.get("games", [])]) for a in pl.get(p["p"], [])]
        players.append(dict(p=p["p"], t=p["t"], r=p["r"], acc=accs))
    have = any(a.get("tier") for x in players for a in x["acc"])
    print("  bootcamp: %d players, %d with a ranked soloQ account" % (len(players), sum(1 for x in players if any(a.get("tier") for a in x["acc"]))))
    return dict(updated=data.get("updated"), have=have, players=players, logos={t: logos_all[t] for t in {x["t"] for x in players} if t in logos_all}, ri=jget(tpl, "SD").get("r", {}))

def main(csv):
    print("reading", csv)
    w = load_event(csv)
    if w.empty: sys.exit("No %s rows on/after %s in %s" % (LEAGUE, MAIN_START, csv))
    print("  %d games, %d players" % (w.gameid.nunique(), w[w.position != "team"].playername.nunique()))
    rt = ratings(csv)
    WD = build_wd(w, rt)
    ST = build_standings(w)
    lastuk = pd.Timestamp(w.date.max()).tz_localize("UTC").tz_convert(TZ); date_s = lastuk.strftime("%b %-d")

    idx = rd("site/index.html")
    logos_all = jget(idx, "LOGOS"); faces_old = jget(idx, "FACES")
    GD = build_game(w, logos_all)
    from types import SimpleNamespace as NS
    extra = [(pd.Timestamp(g["start"]), frozenset(t["code"] for t in g["teams"]), NS(code=g["teams"][0]["code"], result=g["teams"][0]["win"]), NS(code=g["teams"][1]["code"], result=g["teams"][1]["win"]), g["id"]) for g in GD["games"] if g.get("pct")]
    allres = build_recent(w, extra); rec = allres[:4]
    PD = build_profiles(w, faces_old, logos_all)
    PI = load_player_info()
    for n, pl_ in PD["players"].items():
        pl_["bd"] = (PI.get(n) or {}).get("bd"); pl_["contract"] = (PI.get(n) or {}).get("contract")
    print("  player info: %d birthdates, %d contracts" % (sum(1 for p_ in PD["players"].values() if p_["bd"]), sum(1 for p_ in PD["players"].values() if p_["contract"])))
    TD = build_teams(w, PD); G20 = build_g20(w)
    CD = build_champions(w, GD)
    attach_items(w, GD, PD, CD)
    _rg = load_riot_games(); _rev = {v: k for k, v in RIOT_MAP.items()}
    for g_ in GD["games"]:
        m_ = (_rg.get(_rev.get(g_["id"], g_["id"])) or {}).get("mid")
        if m_: g_["mid"] = m_    # Riot match id: lets the game page link to the series Overview and the other games on the live page
    RK, RKUPD, RKTS = build_rankings(csv); HAS = {c: 1 for c in TD['teams']}

    FACES = {p["name"]: p["face"] for p in PD["players"].values() if p["face"]}
    # small (128px) portraits for the leaderboards
    for p in WD["players"]:
        c = [f for f in PLAYER_FILES if f[:-5] == p["t"].lower() + "-" + slug(p["p"])]
        if c:
            im = Image.open("assets/players/" + c[0]).convert("RGBA"); im.thumbnail((128, 128)); FACES[p["p"]] = b64webp(im, 80)
        elif p["p"] not in FACES and p["p"] in faces_old: FACES[p["p"]] = faces_old[p["p"]]
    CH = {}
    for c in WD["champsAll"]:
        k = champ_key(c["c"])
        if k: CH[c["c"]] = champ_icon(k, 68, 88)
        else: print("  no champion icon for", c["c"])

    def stamp(s):
        return re.sub(r"data through [A-Z][a-z]{2} \d+", "data through " + date_s, s)

    # floor & ceiling and closing-out leads (homepage): per team, average end-of-game gold difference in losses and wins, and wins when 2,000+ gold up at 20:00
    T_ = TD["teams"]; gold_ = {(k, g["gid"]): g["gold"] for k, t_ in T_.items() for g in t_["games"]}; fc_pts, fc_lead = [], []
    for k, t_ in T_.items():
        w_, l_ = [], []
        for g in t_["games"]:
            og = gold_.get((g["opp"], g["gid"])); (w_ if g["win"] else l_).append(round(g["gold"] - og) if og is not None else 0)
        if w_ and l_: fc_pts.append(dict(c=k, f=sum(l_) / len(l_), h=sum(w_) / len(w_)))
        gg = [g for g in t_["games"] if G20.get(g["gid"], {}).get(k, -1e9) >= 2000]
        fc_lead.append(dict(c=k, n=len(gg), w=sum(1 for g in gg if g["win"])))
    FCD = dict(pts=fc_pts, lead=fc_lead, n=len(T_), names={k: t_["name"] for k, t_ in T_.items()}, regions={k: t_.get("region") for k, t_ in T_.items()})
    out = ROOT / "dist"
    # index
    s = idx
    for name, val in (("WD", WD), ("FACES", FACES), ("FACESF", FACES), ("CHAMPS", CH), ("SW", ST), ("FCD", FCD)): s = jreplace(s, name, val)
    s = re.sub(r"  var rec = \[\[.*?\]\];\n", lambda m: "  var rec = " + json.dumps(rec, ensure_ascii=False) + ";\n", s, count=1, flags=re.S)
    s = jreplace(s, "rank", RK); s = jreplace(s, "rankUpd", RKUPD); s = jreplace(s, "hasTeam", HAS); s = jreplace(s, "rankTs", RKTS) if "var rankTs" in s else s
    s = jreplace(s, "UP", build_upcoming())
    s = jreplace(s, "SD", build_search(s, WD, CH))
    wr(out / "index.html", stamp(s))
    # champion stats page
    s = rd("site/champions.html")
    for name, val in (("WD", WD), ("CHAMPS", CH)): s = jreplace(s, name, val)
    s = jreplace(s, "SD", build_search(s, WD, CH)); wr(out / "champions.html", stamp(s))
    # power rankings
    s = rd("site/rankings.html"); s = jreplace(s, "rank", RK); s = jreplace(s, "rankUpd", RKUPD); s = jreplace(s, "hasTeam", HAS); s = jreplace(s, "LOGOS", logos_all)
    s = jreplace(s, "SD", build_search(s, WD, CH)); wr(out / "rankings.html", stamp(s))
    # recent results (all series)
    s = rd("site/results.html"); s = jreplace(s, "RES", allres); s = jreplace(s, "LOGOS", logos_all)
    s = jreplace(s, "SD", build_search(s, WD, CH)); wr(out / "results.html", stamp(s))
    # players
    s = rd("site/players.html")
    for name, val in (("WD", WD), ("FACES", FACES), ("FACESF", FACES)): s = jreplace(s, name, val)
    _sd = build_search(s, WD, CH); s = jreplace(s, "TN", {t[0]: t[1] for t in _sd["t"]})   # team code -> full name (alphabetical team grouping)
    s = jreplace(s, "SD", _sd); wr(out / "players.html", stamp(s))
    # data pages
    for fn, val in (("game", GD), ("player", PD), ("team", {k: v for k, v in TD.items() if k != "icons"}), ("champion", CD)):
        s = rd("site/%s.html" % fn); s = jreplace(s, "D", val)
        s = jreplace(s, "SD", build_search(s, WD, CH)); wr(out / (fn + ".html"), stamp(s))
    wr(out / "live-map.json", json.dumps(RIOT_MAP))
    pc = {}   # player on a champion (season): [games, wins, kda, cs/min, dmg/min, kp%, dmg share%, gd@15]
    for nm, pv in PD["players"].items():
        by = {}
        for x in pv["games"]: by.setdefault(re.sub(r"[^a-z]", "", x["champ"].lower()), []).append(x)
        for ck, g in by.items():
            n = len(g); gl = sum(x["gl"] for x in g); gd = [x["gd"] for x in g if x["gd"] is not None]
            tk = sum(x["tk"] for x in g)
            pc["%s|%s" % (re.sub(r"[^a-z0-9]", "", nm.lower()), ck)] = [n, sum(x["win"] for x in g), round((sum(x["k"] + x["a"] for x in g)) / max(1, sum(x["d"] for x in g)), 2),
                round(sum(x["cs"] for x in g) / max(gl, 1), 2), round(sum(x["dmg"] for x in g) / max(gl, 1)), round(100 * sum(x["k"] + x["a"] for x in g) / max(tk, 1)),
                round(100 * sum(x["ds"] for x in g) / n), round(sum(gd) / len(gd)) if gd else None]
    pca = {}   # champion averages over every game at the event, same layout as pc
    byc = {}
    for nm, pv in PD["players"].items():
        for x in pv["games"]: byc.setdefault(re.sub(r"[^a-z]", "", x["champ"].lower()), []).append(x)
    for ck, g in byc.items():
        n = len(g)
        if n < 2: continue
        gl = sum(x["gl"] for x in g); gd = [x["gd"] for x in g if x["gd"] is not None]; tk = sum(x["tk"] for x in g)
        pca[ck] = [n, sum(x["win"] for x in g), round((sum(x["k"] + x["a"] for x in g)) / max(1, sum(x["d"] for x in g)), 2), round(sum(x["cs"] for x in g) / max(gl, 1), 2),
                   round(sum(x["dmg"] for x in g) / max(gl, 1)), round(100 * sum(x["k"] + x["a"] for x in g) / max(tk, 1)), round(100 * sum(x["ds"] for x in g) / n), round(sum(gd) / len(gd)) if gd else None]
    pm = {}   # lane matchups at the event: "role|champion|opposing champion" -> [games, wins, avg gd@15, avg cs diff@15, avg xp diff@15]
    idx = {(x["gid"], x["role"], x["team"]): x for pv in PD["players"].values() for x in pv["games"]}
    cl = lambda c: re.sub(r"[^a-z]", "", c.lower())
    acc = {}
    for pv in PD["players"].values():
        for x in pv["games"]:
            o = idx.get((x["gid"], x["role"], x["opp"]))
            if not o: continue
            e = acc.setdefault("%s|%s|%s" % (x["role"], cl(x["champ"]), cl(o["champ"])), dict(n=0, w=0, gd=[], cs=[], xp=[]))
            e["n"] += 1; e["w"] += x["win"]
            for k_, f_ in (("gd", "gd"), ("cs", "csd"), ("xp", "xpd")):
                if x[f_] is not None: e[k_].append(x[f_])
    for k_, e in acc.items():
        av = lambda v: round(sum(v) / len(v)) if v else None
        pm[k_] = [e["n"], e["w"], av(e["gd"]), av(e["cs"]), av(e["xp"])]
    pb = {}   # each team's best champion per role at the event: "team|role" -> [champion, icon key, player, games, wins, kda, cs/min, dmg share %]
    tr = {}
    for pv in PD["players"].values():
        for x in pv["games"]: tr.setdefault((x["team"], x["role"], x["champ"]), []).append(x)
    cand = {}
    for (t_, r_, c_), g in tr.items():
        n = len(g); gl = sum(x["gl"] for x in g)
        cand.setdefault("%s|%s" % (t_, r_), []).append([c_, g[0]["ic"], max(set(x["player"] for x in g), key=lambda p_: sum(1 for x in g if x["player"] == p_)), n, sum(x["win"] for x in g),
                                                       round(sum(x["k"] + x["a"] for x in g) / max(1, sum(x["d"] for x in g)), 2), round(sum(x["cs"] for x in g) / max(gl, 1), 1), round(100 * sum(x["ds"] for x in g) / n)])
    for k_, L in cand.items():
        L = [c for c in L if c[4] > 0]   # a pick to watch needs at least one win
        if not L: continue
        pool = [c for c in L if c[3] >= 2] or L
        pb[k_] = sorted(pool, key=lambda c: (-c[4] / c[3], -c[3], -c[5]))[0]
    pbi = {c[1]: champ_icon(c[1], 36, 72) for c in pb.values() if c[1]}
    ps = {"ri": jget(rd("site/bootcamp.html"), "SD").get("r", {}), "p": {"%s|%s" % (p["t"], p["r"]): [p["p"], p["rt"], p["kda"], p["cs"], p["gd"], p["dpm"], p["kp"], p["ds"], p["g"]] for p in WD["players"]}, "f": {"%s|%s" % (p["t"], p["r"]): FACES[p["p"]] for p in WD["players"] if p["p"] in FACES}, "t": {c: team_season(v["games"]) for c, v in TD["teams"].items()}}
    s = rd("site/match.html")   # the one match page: game data (D), search, season stats (PS, PC) and the Riot->Oracle's Elixir game map
    for nm, val in (("D", GD), ("PS", ps), ("PC", pc), ("PM", pm), ("PB", pb), ("PBI", pbi), ("MAP0", RIOT_MAP), ("TR", {r[2]: i + 1 for i, r in enumerate(RK)})): s = jreplace(s, nm, val)
    wr(out / "match.html", stamp(jreplace(s, "SD", build_search(s, WD, CH))))
    wr(out / "live.html", '<!doctype html><meta charset="utf-8"><title>Match</title><script>var h=location.hash.replace(/^#live\\//,"#");location.replace("match.html"+h)</script>')   # old links   # season stats for the live page's role-by-role team comparison   # live game page: polls Riot's feed in the browser, no build-time data
    s = rd("site/bootcamp.html"); s = jreplace(s, "BC", build_bootcamp(WD, logos_all, s)); s = jreplace(s, "SD", build_search(s, WD, CH)); wr(out / "bootcamp.html", stamp(s))
    wr(out / ".nojekyll", "")
    import build_scopes
    _ic = {}
    def _icon(c):
        if c not in _ic:
            k = champ_key(c); _ic[c] = champ_icon(k, 68, 80) if k else None
        return _ic[c]
    build_scopes.build(csv, out / "data", lambda n: CODE.get(NAME_FIX.get(n, n)) or re.sub(r"[^A-Z0-9]", "", "".join(x[0] for x in n.split()).upper())[:4] or n[:3].upper(), _icon)
    if (ROOT / "site" / "filters.js").exists(): wr(out / "filters.js", rd("site/filters.js"))

    print("done - %d pages written to dist/ (data through %s)" % (len(list(out.glob("*.html"))), date_s))

if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else CSV_DEFAULT)
