"""Opponent adjustment, match ratings and tournament aggregation."""
import numpy as np, pandas as pd
import config as C
import data, elo, features as F

def fit_opp_slope(players, elo_df, before):
    """OLS of league-role standardised performance on own/opponent pre-match Elo, using ONLY games before `before`.
    Returns slopes per 100 Elo points, standard errors and n."""
    p = players[(players["date"] < before)].copy()
    p = p[p.groupby(["league", "position"])["gameid"].transform("size") >= 150]
    p = F.derive(p)
    p = F.zscores(p, ["league", "position"])
    p, _ = F.composite(p, ["league", "position"])
    e = elo_df[["gameid", "teamname", "elo_pre", "opp_elo_pre"]]
    p = p.merge(e, on=["gameid", "teamname"], how="inner")
    p = p[p["date"] >= p["date"].min() + pd.Timedelta(days=C.BURN_IN_DAYS)].dropna(subset=["z_obs", "elo_pre", "opp_elo_pre"])
    X = np.column_stack([np.ones(len(p)), (p["elo_pre"] - p["elo_pre"].mean()) / 100, (p["opp_elo_pre"] - p["opp_elo_pre"].mean()) / 100])
    y = p["z_obs"].to_numpy()
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    res = y - X @ beta
    # cluster-robust by game to respect the 10 correlated player rows per game
    xtx_inv = np.linalg.inv(X.T @ X)
    meat = np.zeros((3, 3))
    for _, idx in p.groupby("gameid").indices.items():
        s = X[idx].T @ res[idx]; meat += np.outer(s, s)
    se = np.sqrt(np.diag(xtx_inv @ meat @ xtx_inv))
    return dict(b_own=float(beta[1]), b_opp=float(beta[2]), se_own=float(se[1]), se_opp=float(se[2]), n=int(len(p)), games=int(p["gameid"].nunique()))

def match_table(players, teams, params=None):
    """Full pipeline -> one row per Worlds player-game with raw and opponent-adjusted ratings."""
    P = dict(k_elo=C.ELO_K, mode=C.ELO_INIT_MODE, weights=C.WEIGHTS, adj=True, scale=C.RATING_SCALE, cap=C.OPP_ADJ_CAP, slope=None)
    P.update(params or {})
    elo_df = P.get("elo_df")
    if elo_df is None:
        elo_df, _ = elo.run(teams, P["k_elo"], P["mode"])
    w = data.worlds(players)
    first = w["date"].min()
    slope = P["slope"] or fit_opp_slope(players, elo_df, first)
    w = F.derive(w)
    w = F.zscores(w, "position")
    w, cats = F.composite(w, "position", weights=P["weights"])
    w = w.merge(elo_df[["gameid", "teamname", "elo_pre", "opp_elo_pre", "p_win", "opp"]], on=["gameid", "teamname"], how="left")
    ref = w["opp_elo_pre"].mean()
    b = min(slope["b_opp"], 0.0)                                   # a stronger opponent can only make the game harder
    # expected perf vs this opponent = b*(opp-ref)/100 ; adjustment = -expected, capped
    w["opp_adj"] = (-(b * (w["opp_elo_pre"] - ref) / 100)).clip(-P["cap"], P["cap"]) if P["adj"] else 0.0
    w["z_adj"] = w["z_obs"] + w["opp_adj"]
    w["rating_raw"] = (50 + P["scale"] * w["z_obs"]).clip(1, 100)
    w["rating_match"] = (50 + P["scale"] * w["z_adj"]).clip(1, 100)
    w.attrs["slope"], w.attrs["ref_elo"], w.attrs["cats"], w.attrs["elo_df"] = slope, float(ref), cats, elo_df
    return w.sort_values(["date", "gameid"])

def aggregate(m, k=C.K_SHRINK, scale=C.RATING_SCALE, stage=None):
    """Tournament rating with small-sample shrinkage toward 50 and a shrunk standard error (vectorised)."""
    x = (m if stage is None else m[m["stage"] == stage]).sort_values("date")
    pooled_sd = x["rating_match"].std()
    ctc = ["ct_" + c for c in ("combat", "economy", "objectives", "damage_survival", "vision", "winning")]
    g = x.groupby("playerid")
    r = g.agg(player=("playername", "last"), team=("teamname", "last"), role=("position", "last"), games=("gameid", "size"),
              avg_raw_z=("z_obs", "mean"), avg_adj_z=("z_adj", "mean"), avg_match_rating=("rating_match", "mean"),
              avg_rating_unadjusted=("rating_raw", "mean"), sd=("rating_match", "std"), opp_adj_pts=("opp_adj", "mean"),
              **{c: (c, "mean") for c in ctc}).reset_index()
    n = r["games"]; sh = n / (n + k)
    sd = r["sd"].where(n > 1, pooled_sd).fillna(pooled_sd)
    s = np.sqrt(sh * sd ** 2 + (1 - sh) * pooled_sd ** 2)       # blend own sd with pooled sd so n=1 stays finite
    r["rating"] = 50 + sh * (r["avg_match_rating"] - 50)
    r["se"] = sh * s / np.sqrt(n)
    r["opp_adj_pts"] *= scale
    for c in ctc: r[c] *= scale
    r = r.drop(columns="sd")
    r["ci_low"], r["ci_high"] = r["rating"] - 1.96 * r["se"], r["rating"] + 1.96 * r["se"]
    r = r.sort_values("rating", ascending=False).reset_index(drop=True)
    r.insert(0, "rank", r.index + 1)
    r["role_rank"] = r.groupby("role")["rating"].rank(ascending=False, method="first").astype(int)
    return r
