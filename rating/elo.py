"""Team Elo with strictly pre-match ratings (no look-ahead)."""
import numpy as np, pandas as pd
import config as C

def init_ratings(teams, mode=C.ELO_INIT_MODE, flat=C.ELO_FLAT, tiers=C.TIER_INIT):
    """Initial rating per team from the league of its first domestic appearance (tier prior) or a flat value."""
    dom = teams[~teams["league"].isin(C.INTERNATIONAL)].sort_values("date")
    first = dom.groupby("teamname")["league"].first()
    out = {}
    for t in teams["teamname"].unique():
        if mode == "flat":
            out[t] = flat
            continue
        lg = first.get(t)
        out[t] = tiers["tier1"] if lg in C.TIER1 else tiers["tier2"] if lg in C.TIER2 else tiers["tier3"]
    return out

def expected(a, b):
    return 1.0 / (1.0 + 10 ** ((b - a) / 400.0))

def run(teams, k=C.ELO_K, mode=C.ELO_INIT_MODE, flat=C.ELO_FLAT):
    """Walk games chronologically. Returns a per-team-game frame with elo_pre, opp_elo_pre, p_win."""
    r = init_ratings(teams, mode, flat)
    g = teams.sort_values(["date", "gameid"])
    rows = []
    for gid, x in g.groupby("gameid", sort=False):
        if len(x) != 2:
            continue
        a, b = x.iloc[0], x.iloc[1]
        ea, eb = r[a.teamname], r[b.teamname]
        pa = expected(ea, eb)
        sa = float(a.result)
        for t, o, e, oe, p in ((a, b, ea, eb, pa), (b, a, eb, ea, 1 - pa)):
            rows.append(dict(gameid=gid, date=t.date, league=t.league, teamname=t.teamname, opp=o.teamname, side=t.side,
                             elo_pre=e, opp_elo_pre=oe, p_win=p, result=float(t.result)))
        r[a.teamname] = ea + k * (sa - pa)
        r[b.teamname] = eb + k * ((1 - sa) - (1 - pa))
    return pd.DataFrame(rows), r

def scores(df):
    """Log loss and Brier score of the pre-match win probability (one row per team-game; each game counted twice, symmetric)."""
    p = df["p_win"].clip(1e-6, 1 - 1e-6).to_numpy(); y = df["result"].to_numpy()
    return dict(log_loss=float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p))), brier=float(np.mean((p - y) ** 2)), n_games=len(df) // 2)
