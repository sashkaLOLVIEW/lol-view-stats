"""Filterable data for every league in the Oracle's Elixir CSV (dist/data/*.json).

The pages keep their embedded Worlds data as the default. When a visitor picks another league / split / stage / year in the
filter bar (site/filters.js), the browser loads these files and aggregates them into the same shapes the pages already draw.

dist/data/meta.json        lookups: leagues (with years, splits), players, teams, champions, patches
dist/data/lg-<LEAGUE>.json column arrays, one row per player-game (rows) / per game (games) / per team-game (teams)
dist/data/champs.json      champion icons (68px webp, base64) keyed by champion name
"""
import json, re, sys
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "rating"))
POS = ["top", "jng", "mid", "bot", "sup"]


def _clean(v, nd=None):
    out = []
    for x in v:
        if x is None or (isinstance(x, float) and (np.isnan(x) or np.isinf(x))): out.append(None)
        elif nd is None: out.append(int(x) if float(x).is_integer() else float(x))
        else: out.append(int(round(x)) if nd == 0 else round(float(x), nd))
    return out


def match_z(df):
    """League-relative composite z-score per player-game (same features as the Worlds rating, without the Elo opponent adjustment)."""
    import features as F
    p = df[(df.position != "team") & (df.datacompleteness == "complete")].copy()
    p = F.derive(p); grp = ["league", "year", "position"]
    p = F.zscores(p, grp); p, _ = F.composite(p, grp)
    k = "playerid" if "playerid" in p else "playername"
    return {(g, n): v for g, n, v in zip(p.gameid, p[k], p.z_obs) if pd.notna(v)}


def build(csv, out_dir, code_of, icons_fn, leagues=None, current=None, team_leagues=None):
    df = pd.read_csv(csv, low_memory=False)
    df["date"] = pd.to_datetime(df["date"])
    df = df[df.gameid.notna()].copy()
    if leagues: df = df[df.league.isin(leagues)].copy()
    if team_leagues:   # only teams (and their players) that play in these domestic leagues; their games at international events stay
        tier = set(df[df.league.isin(team_leagues)].teamname.dropna())
        gids = set(df[df.teamname.isin(tier)].gameid)
        df = df[df.gameid.isin(gids) & df.teamname.isin(tier)].copy()
    df["split"] = df["split"].fillna("")
    import shutil
    out_dir = Path(out_dir); shutil.rmtree(out_dir, ignore_errors=True); out_dir.mkdir(parents=True, exist_ok=True)
    z = match_z(df)
    zkey = "playerid" if "playerid" in df else "playername"

    pl = df[df.position != "team"]
    players = sorted(pl.playername.dropna().unique(), key=str.lower); pidx = {n: i for i, n in enumerate(players)}
    teams = sorted(df.teamname.dropna().unique(), key=str.lower); tidx = {n: i for i, n in enumerate(teams)}
    champs = sorted(set(pl.champion.dropna()) | {b for c in ("ban1", "ban2", "ban3", "ban4", "ban5") for b in df[c].dropna()}, key=str.lower); cidx = {n: i for i, n in enumerate(champs)}
    patches = sorted({"%.2f" % x for x in df.patch.dropna()}, key=float); pt_idx = {n: i for i, n in enumerate(patches)}
    meta = dict(current=current, leagues={}, players=players, teams=[[t, code_of(t)] for t in teams], champs=champs, patches=patches, built=str(df.date.max())[:10])

    pix, tix = {}, {}
    for lg, d in df.groupby("league"):
        d = d.sort_values(["date", "gameid"]); gids = list(dict.fromkeys(d.gameid)); gi = {g: i for i, g in enumerate(gids)}
        splits = sorted(set(d.split)); si = {s: i for i, s in enumerate(splits)}
        tm = d[d.position == "team"]
        gm = d.drop_duplicates("gameid").set_index("gameid").loc[gids]
        blue = tm[tm.side == "Blue"].set_index("gameid").reindex(gids); red = tm[tm.side == "Red"].set_index("gameid").reindex(gids)
        games = dict(id=gids, d=[str(x)[:16] for x in gm.date], y=_clean(gm.year), sp=[si[s] for s in gm.split], po=_clean(gm.playoffs.fillna(0)), pt=[pt_idx.get("%.2f" % x, -1) if pd.notna(x) else -1 for x in gm.patch],
                     len=_clean(gm.gamelength), bt=[tidx.get(x, -1) if isinstance(x, str) else -1 for x in blue.teamname], rt=[tidx.get(x, -1) if isinstance(x, str) else -1 for x in red.teamname],
                     bw=_clean(blue.result), g=_clean(gm.game), cp=[1 if c == "complete" else 0 for c in gm.datacompleteness])
        p = d[d.position != "team"].copy()
        tk = tm.set_index(["gameid", "side"])["teamkills"].to_dict()
        zz = [z.get((g, k)) for g, k in zip(p.gameid, p[zkey])]
        rows = dict(g=[gi[x] for x in p.gameid], s=[0 if x == "Blue" else 1 for x in p.side], pos=[POS.index(x) for x in p.position], p=[pidx[x] for x in p.playername],
                    t=[tidx[x] for x in p.teamname], c=[cidx.get(x, -1) if isinstance(x, str) else -1 for x in p.champion], w=_clean(p.result),
                    k=_clean(p.kills), d=_clean(p.deaths), a=_clean(p.assists), tk=_clean([tk.get((g, s)) for g, s in zip(p.gameid, p.side)]),
                    cs=_clean(p["total cs"]), dmg=_clean(p.damagetochampions), gold=_clean(p.totalgold), dpm=_clean(p.dpm, 1), cspm=_clean(p.cspm, 2), gpm=_clean(p["earned gpm"], 1),
                    ds=_clean(p.damageshare, 4), gd=_clean(p.golddiffat15), csd=_clean(p.csdiffat15), xpd=_clean(p.xpdiffat15), vs=_clean(p.vspm, 2), z=_clean(zz, 3), gs=_clean(p.earnedgoldshare, 4), wpm=_clean(p.wpm, 2), wcpm=_clean(p.wcpm, 2), dtm=_clean(p.damagetakenperminute, 0))
        t = tm.copy()
        def col(c, nd=None): return _clean(t[c], nd) if c in t else [None] * len(t)
        teamsb = dict(g=[gi[x] for x in t.gameid], s=[0 if x == "Blue" else 1 for x in t.side], t=[tidx[x] for x in t.teamname], w=col("result"), k=col("teamkills"), d=col("teamdeaths"),
                      tw=col("towers"), dr=col("dragons"), ba=col("barons"), he=col("heralds"), gr=col("void_grubs"), fb=col("firstblood"), ft=col("firsttower"), gold=col("totalgold"),
                      bans=[[cidx.get(x, -1) if isinstance(x, str) else -1 for x in r] for r in t[["ban1", "ban2", "ban3", "ban4", "ban5"]].itertuples(index=False)])
        spn = [splits[i] for i in games["sp"]]
        gk = [(games["y"][i], spn[i], 1 << int(bool(games["po"][i])), games["d"][i][:10]) for i in range(len(gids))]
        ltup = {}
        for y_, sp_, m_, _d in gk: ltup[(y_, sp_)] = ltup.get((y_, sp_), 0) | m_
        def acc(e, k, m_, d_):
            o = e.get(k, [0, ""]); e[k] = [o[0] | m_, max(o[1], d_)]
        for i in range(len(rows["g"])):
            y_, sp_, m_, d_ = gk[rows["g"][i]]; acc(pix.setdefault(players[rows["p"][i]], {}), (lg, y_, sp_), m_, d_)
        for i in range(len(teamsb["g"])):
            y_, sp_, m_, d_ = gk[teamsb["g"][i]]; acc(tix.setdefault(teams[teamsb["t"][i]], {}), (lg, y_, sp_), m_, d_)
        (out_dir / ("lg-%s.json" % re.sub(r"[^A-Za-z0-9_-]", "_", lg))).write_text(json.dumps(dict(games=games, rows=rows, teams=teamsb), separators=(",", ":")), encoding="utf-8")
        meta["leagues"][lg] = dict(tuples=[[y_, sp_, m_] for (y_, sp_), m_ in sorted(ltup.items())], n=len(gids), years=sorted(int(x) for x in set(d.year)), splits=splits, first=str(d.date.min())[:10], last=str(d.date.max())[:10])
    meta["pix"] = {k: [[a, b, c, m[0], m[1]] for (a, b, c), m in sorted(v.items())] for k, v in pix.items()}
    meta["tix"] = {k: [[a, b, c, m[0], m[1]] for (a, b, c), m in sorted(v.items())] for k, v in tix.items()}
    (out_dir / "meta.json").write_text(json.dumps(meta, separators=(",", ":")), encoding="utf-8")
    (out_dir / "champs.json").write_text(json.dumps({c: icons_fn(c) for c in champs if icons_fn(c)}, separators=(",", ":")), encoding="utf-8")
    print("  filter data: %d leagues, %d players, %d teams, %d champions -> %s" % (len(meta["leagues"]), len(players), len(teams), len(champs), out_dir))
