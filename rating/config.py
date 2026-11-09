"""Central configuration. Every provisional parameter lives here so it can be audited and changed."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "out"
DATA_CSV = ROOT / "data" / "2026_LoL_esports_match_data_from_OraclesElixir.csv"

# --- tournament filter -------------------------------------------------------
LEAGUE = "WLDs"            # Oracle's Elixir tag used for Worlds 2026
YEAR = 2026
# The CSV has no stage column for Worlds (split/playoffs are empty), so stages are inferred from dates
# and team sets (verified by inspection, see METHODOLOGY.md section 1).
STAGES = [("2026-09-17", "2026-09-20", "Regional qualifier (WLDs-tagged)"),
          ("2026-10-15", "2026-10-19", "Play-Ins"),
          ("2026-10-23", "2099-01-01", "Main stage")]

# --- Elo (team strength) -----------------------------------------------------
ELO_K = 24                 # chosen by time-ordered log loss on Worlds games (see validation)
ELO_INIT_MODE = "tier"     # "tier" or "flat"
ELO_FLAT = 1500
TIER_INIT = {"tier1": 1560, "tier2": 1500, "tier3": 1440}
TIER1 = {"LCK", "LPL"}
TIER2 = {"LEC", "LCS", "LCP", "CBLOL"}
INTERNATIONAL = {"MSI", "EWC", "FST", "WSCI", "CCWS", "WLDs", "WLRQ", "AC", "DCGI", "DCup", "AM"}

# --- category weights (provisional hypotheses from the brief) -----------------
WEIGHTS = {"combat": .25, "economy": .20, "objectives": .20, "damage_survival": .15, "vision": .10, "winning": .10}

# --- feature -> category, with within-category weights ------------------------
# sign = +1 higher is better, -1 lower is better
FEATURES = {
    "combat": {"kp": (.50, +1), "kill_share": (.30, +1), "fb_involve": (.20, +1)},
    "economy": {"gpm": (.45, +1), "cspm": (.30, +1), "gold_share": (.25, +1)},
    "objectives": {"gd15": (.30, +1), "xpd15": (.25, +1), "csd15": (.15, +1), "gd10": (.15, +1), "xpd10": (.15, +1)},
    "damage_survival": {"dpm": (.40, +1), "dmg_per_gold": (.25, +1), "deaths_pm": (.35, -1)},
    "vision": {"vspm": (.50, +1), "wpm": (.20, +1), "wcpm": (.20, +1), "cwpm": (.10, +1)},
}
# --- supports are judged by different stats: CS, gold share and damage mostly measure the other roles, not the support's contribution ---
WEIGHTS_SUP = {"combat": .30, "economy": .05, "objectives": .15, "damage_survival": .10, "vision": .30, "winning": .10}
FEATURES_SUP = {
    "combat": {"kp": (.50, +1), "apm": (.35, +1), "fb_involve": (.15, +1)},                       # kill participation and assists per minute, not kills
    "economy": {"gpm": (1.0, +1)},
    "objectives": {"gd10": (.25, +1), "xpd10": (.25, +1), "gd15": (.25, +1), "xpd15": (.25, +1)},  # lane influence; CS diff is meaningless for a support
    "damage_survival": {"deaths_pm": (.75, -1), "dpm": (.25, +1)},
    "vision": {"vspm": (.45, +1), "wpm": (.25, +1), "wcpm": (.20, +1), "cwpm": (.10, +1)},
}
WIN_WITHIN = {"relative_to_team": .75, "result": .25}   # composition of category F

# --- scaling and shrinkage ----------------------------------------------------
Z_CLIP = 3.0
RATING_SCALE = 12.0        # rating = 50 + RATING_SCALE * z
DISPLAY_RATING = lambda r: min(99.9, max(1.0, 68 + 3.3 * (r - 50)))  # site display scale (best players in the 90s)
K_SHRINK = 5
MIN_GAMES_LEADERBOARD = 1

# --- opponent adjustment ------------------------------------------------------
OPP_ADJ_CAP = 0.35         # max |adjustment| in z units
BURN_IN_DAYS = 60          # games before this are used for Elo warm-up only when fitting the slope
