"""Feature engineering and role-relative standardisation."""
import numpy as np, pandas as pd
import config as C

BASE = ["kp", "kill_share", "fb_involve", "gpm", "cspm", "gold_share", "gd15", "xpd15", "csd15", "gd10", "xpd10",
        "dpm", "dmg_per_gold", "deaths_pm", "vspm", "wpm", "wcpm", "cwpm"]

def derive(p):
    p = p.copy()
    mins = p["gamelength"] / 60.0
    tk = p["teamkills"].replace(0, np.nan)
    p["kp"] = (p["kills"] + p["assists"]) / tk
    p["kill_share"] = p["kills"] / tk
    p["fb_involve"] = ((p["firstbloodkill"] == 1) | (p["firstbloodassist"] == 1)).astype(float)
    p["gpm"] = p["earned gpm"]
    p["gold_share"] = p["earnedgoldshare"]
    p["gd15"], p["xpd15"], p["csd15"] = p["golddiffat15"], p["xpdiffat15"], p["csdiffat15"]
    p["gd10"], p["xpd10"] = p["golddiffat10"], p["xpdiffat10"]
    p["dmg_per_gold"] = p["dpm"] / p["earned gpm"]
    p["deaths_pm"] = p["deaths"] / mins
    p["cwpm"] = p["controlwardsbought"] / mins
    p["role"] = p["position"]
    return p

def zscores(p, group):
    """Winsorised within-group z-scores for every base feature -> columns z_<feature> (sign applied later)."""
    p = p.copy()
    for f in BASE:
        g = p.groupby(group)[f]
        mu, sd = g.transform("mean"), g.transform("std")
        p["z_" + f] = ((p[f] - mu) / sd.replace(0, np.nan)).clip(-C.Z_CLIP, C.Z_CLIP)
    return p

def category_scores(p, weights=None, feats=None):
    """Weighted mean of signed z-scores per category. Missing features are dropped and weights renormalised."""
    feats = feats or C.FEATURES
    p = p.copy()
    for cat, fs in feats.items():
        num = 0; den = 0
        for f, (w, s) in fs.items():
            z = p["z_" + f] * s
            num = num + z.fillna(0) * w
            den = den + z.notna().astype(float) * w
        p["cat_" + cat] = num / den.replace(0, np.nan)
    return p

def composite(p, group, weights=None, feats=None, win_within=None):
    """Composite match score z_obs (standardised per group) and per-category contributions in z units."""
    W = dict(weights or C.WEIGHTS)
    ww = win_within or C.WIN_WITHIN
    p = category_scores(p, feats=feats)
    cats = list(feats.keys() if feats else C.FEATURES.keys())
    base_w = {c: W[c] for c in cats}
    s = sum(base_w.values())
    p["ae"] = sum(p["cat_" + c] * base_w[c] / s for c in cats)                # composite of categories A-E
    team_sum = p.groupby(["gameid", "teamname"])["ae"].transform("sum")
    team_n = p.groupby(["gameid", "teamname"])["ae"].transform("count")
    p["ae_rel"] = p["ae"] - (team_sum - p["ae"]) / (team_n - 1).replace(0, np.nan)   # vs the four teammates
    g = p.groupby(group)["ae_rel"]
    p["z_rel"] = ((p["ae_rel"] - g.transform("mean")) / g.transform("std")).clip(-C.Z_CLIP, C.Z_CLIP)
    p["z_res"] = (p["result"] - .5) / .5
    p["cat_winning"] = ww["relative_to_team"] * p["z_rel"].fillna(0) + ww["result"] * p["z_res"]
    allc = cats + ["winning"]
    p["comp"] = sum(p["cat_" + c] * W[c] for c in allc)
    g = p.groupby(group)["comp"]
    mu, sd = g.transform("mean"), g.transform("std")
    p["z_obs"] = (p["comp"] - mu) / sd
    for c in allc:
        cm = p.groupby(group)["cat_" + c].transform("mean")
        p["ct_" + c] = W[c] * (p["cat_" + c] - cm) / sd
    return p, allc
