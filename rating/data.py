"""Load, validate and filter the Oracle's Elixir CSV."""
import pandas as pd
import config as C

REQUIRED = ["gameid", "league", "date", "position", "playername", "teamname", "side", "result", "gamelength", "kills", "deaths",
            "assists", "teamkills", "damageshare", "dpm", "earned gpm", "earnedgoldshare", "cspm", "vspm", "wpm", "wcpm",
            "controlwardsbought", "golddiffat10", "xpdiffat10", "golddiffat15", "xpdiffat15", "csdiffat15", "firstbloodkill",
            "firstbloodassist", "datacompleteness", "patch"]

def load(path=C.DATA_CSV):
    df = pd.read_csv(path, low_memory=False).copy()
    missing = [c for c in REQUIRED if c not in df.columns]
    if missing:
        raise ValueError(f"CSV is missing required columns: {missing}")
    df["date"] = pd.to_datetime(df["date"])
    return df

def stage_of(d):
    for a, b, name in C.STAGES:
        if pd.Timestamp(a) <= d < pd.Timestamp(b):
            return name
    return "Other"

def split(df):
    """Return (team_rows, player_rows) restricted to complete games of year C.YEAR."""
    df = df[(df["year"] == C.YEAR) & (df["datacompleteness"] == "complete")]
    teams = df[df["position"] == "team"].copy()
    players = df[df["position"] != "team"].copy()
    return teams, players

def worlds(players):
    w = players[players["league"] == C.LEAGUE].copy()
    w["stage"] = w["date"].map(stage_of)
    return w
