# Key points

Changes or decisions we are not sure about yet. Come back to these later.

## 1. Keep a permanent copy of the post-game data (opened 5 Nov 2026)
Right now the saved game data lives only in the GitHub Actions cache (Riot games file, Oracle's Elixir CSV) and in the per-league files the site serves. There is no permanent archive.

Option on the table: at the end of each build, commit `data/riot_games.json` to a separate `data` branch (only when it changed).
- Optional: a weekly dated snapshot of the Oracle's Elixir CSV (about 76 MB each, so it grows the repo; check Oracle's Elixir terms before republishing it).
- The main site and its build would not change.
- Still to decide: Riot games file only, or the weekly CSV snapshot too.

## 2. Roster Google Sheet is still private (opened 5 Nov 2026)
The site reads the roster sheet in the update Action, which needs "Anyone with the link can view". Until that is set, the site uses the committed snapshot and most flags/ages are missing.

## 3. DPM calculation (opened earlier)
The homepage and player profile can show different DPM values. Owner is investigating; no change made yet.
