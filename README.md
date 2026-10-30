# LoL View Stats

Fan-made League of Legends esports stats site. Data: [Oracle's Elixir](https://oracleselixir.com) (credited on every page).

## How it works

| File | What it does |
|---|---|
| `site/*.html` | The six hand-designed pages. They are **templates**: every data block inside is replaced on each build. Edit design/layout here. |
| `build.py` | Reads the CSV, recalculates ratings, standings, recent results, graphs and search, writes the finished site to `dist/`. |
| `fetch_data.py` | Downloads the newest CSV from Oracle's Elixir's public Google Drive folder into `data/` (not committed). |
| `rating/` | The player rating model (Elo-adjusted role z-scores). |
| `assets/` | Player portraits and champion icons used by the build. |
| `.github/workflows/update.yml` | Runs fetch + build + publish every 6 hours, on every push, and on demand. |

Run locally: `pip install -r requirements.txt`, put the CSV in `data/`, then `python build.py`.

## Things that are edited by hand (the build never touches them)

- **Upcoming Matches** (`var up` in `site/index.html`), currently sample fixtures.
- **Knockout bracket** (`var KO` in `site/index.html`).
- **Global Power Rankings** list and its "Updated" stamp.
- **Flags** (`NAT` in `site/team.html`) and **team logos** (`LOGOS` in `site/index.html`).

## Item builds

`fetch_items.py` reads each finished Worlds game from Riot's live stats feed (final inventory per player) into `data/items_cache.json`; `build.py` matches those games to Oracle's Elixir by teams, game number and start time, and embeds item icons from Riot Data Dragon. If the feed is down the site simply shows no items.

## Player age and contract

`fetch_player_info.py` looks every player up on Leaguepedia (birthdate, contract end). Type anything it misses into `config/player_info.csv`
(`player,birthdate,contract`, birthdate as `1996-05-07`, contract as `2027-11-30` or `Nov 2027`); your values always win.

## Settings at the top of `build.py`

`LEAGUE`, `MAIN_START`, `CODE` (team name to short code), `REGION`. A new team that is not in `CODE` stops the build with a clear message.

## If the daily download fails

1. Re-run the workflow from the Actions tab (Google sometimes refuses once and accepts later).
2. Add a free Google API key as a repository secret named `DRIVE_API_KEY` (Settings, Secrets and variables, Actions). The download then uses the official API instead.
3. Last resort: run `fetch_data.py` yourself or download the CSV by hand, then `python build.py`.

Scheduled workflows on GitHub pause after 60 days without any repository activity. Any commit, or the "Run workflow" button, switches them back on.
