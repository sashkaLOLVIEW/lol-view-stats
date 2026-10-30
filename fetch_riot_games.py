#!/usr/bin/env python3
"""Save every finished game of the event, straight from Riot's lolesports live-stats feed, so the site can show it minutes after it ends
(without waiting for Oracle's Elixir).

    python fetch_riot_games.py       -> data/riot_games.json   (one entry per Riot game id; finished games never change, so each is fetched once)

Needs only a handful of feed requests per game (final frame, final details, one gold sample every 5 minutes).
Any failure leaves the cache as it is and exits 0, so the site still builds.
"""
import json, sys, time, datetime as dt
from pathlib import Path
import fetch_items as FI

OUT = FI.ROOT / "data" / "riot_games.json"
FORMAT = 1
BUDGET = 300      # seconds of feed requests per run
get, iso, fmt, floor10 = FI.get, FI.iso, FI.fmt, FI.floor10
FEED, GW = FI.FEED, FI.GW
ROLE_OF = {"top": "top", "jungle": "jng", "mid": "mid", "bottom": "bot", "support": "sup"}

def fetch_game(game, e, bo):
    gid = game["id"]
    w0 = get(FEED + "/window/" + gid)
    md = w0["gameMetadata"]; t0 = iso(w0["frames"][0]["rfc460Timestamp"])
    wend = get(FEED + "/window/" + gid, startingTime=fmt(floor10(t0 + dt.timedelta(hours=3))))
    fr = wend.get("frames") or []
    if not fr or fr[-1].get("gameState") != "finished": raise RuntimeError("no finished frame")
    lf = fr[-1]; tend = iso(lf["rfc460Timestamp"]); length = int((tend - t0).total_seconds())
    det = get(FEED + "/details/" + gid, startingTime=fmt(floor10(tend - dt.timedelta(seconds=30))))
    dpl = {p["participantId"]: p for p in (det.get("frames") or [{}])[-1].get("participants") or []}
    series = []
    m = 5
    while t0 + dt.timedelta(minutes=m) < tend - dt.timedelta(seconds=30):
        try:
            f = (get(FEED + "/window/" + gid, startingTime=fmt(floor10(t0 + dt.timedelta(minutes=m)))).get("frames") or [None])[0]
            if f: series.append([m, f["blueTeam"]["totalGold"] - f["redTeam"]["totalGold"]])
        except Exception: pass
        m += 5; time.sleep(0.12)
    byid = {t["id"]: t for t in e["match"]["teams"]}
    teams = []
    for side in ("blue", "red"):
        tmeta = md[side + "TeamMetadata"]; rt = byid.get(tmeta["esportsTeamId"]) or {}; ft = lf[side + "Team"]
        code = (rt.get("code") or "").upper()
        players = []
        for pm in tmeta["participantMetadata"]:
            pos = ROLE_OF.get(pm["role"])
            if not pos: continue
            fp = next((p for p in ft["participants"] if p["participantId"] == pm["participantId"]), {})
            dp = dpl.get(pm["participantId"]) or {}; pk = dp.get("perkMetadata") or {}
            nm = pm.get("summonerName") or ""
            players.append(dict(pos=pos, name=nm[len(code) + 1:] if code and nm.upper().startswith(code + " ") else nm, champ=pm.get("championId"),
                                k=fp.get("kills", 0), d=fp.get("deaths", 0), a=fp.get("assists", 0), cs=fp.get("creepScore", 0), gold=fp.get("totalGold", 0),
                                share=dp.get("championDamageShare") or 0, items=[i for i in (dp.get("items") or []) if i],
                                style=pk.get("styleId"), sub=pk.get("subStyleId"), perks=pk.get("perks")))
        teams.append(dict(side=side, code=code, name=rt.get("name") or code, k=ft.get("totalKills", 0), gold=ft.get("totalGold", 0), towers=ft.get("towers", 0),
                          barons=ft.get("barons", 0), inhib=ft.get("inhibitors", 0), dragons=[str(x).lower() for x in ft.get("dragons") or []], players=players))
    series.append([round(length / 60, 1), teams[0]["gold"] - teams[1]["gold"]])
    # Riot's feed does not say who won; the team that took more inhibitors, then towers, then gold did (the nexus falls after an inhibitor)
    score = lambda t: t["inhib"] * 1e6 + t["towers"] * 1e4 + t["gold"]
    return dict(id=gid, v=FORMAT, number=game["number"], bo=bo, start=fmt(t0), patch=md.get("patchVersion"), len=length, blue_win=score(teams[0]) >= score(teams[1]), teams=teams, gold=[[0, 0]] + series)

def main():
    try: cache = json.loads(OUT.read_text(encoding="utf-8"))
    except Exception: cache = {}
    ms = FI.finished_matches(); new = bad = skipped = 0
    print("finished matches:", len(ms), "| games already saved:", len(cache))
    t_start = time.time()
    for mid, e in sorted(ms.items(), key=lambda x: x[1]["startTime"]):
        try: games = get(GW + "/getEventDetails", hl="en-US", id=mid)["data"]["event"]["match"]["games"]
        except Exception as ex: print("  match", mid, "details failed:", ex); bad += 1; continue
        bo = int(((e["match"].get("strategy") or {}).get("count")) or 0)
        for g in games:
            old = cache.get(g["id"])
            if g.get("state") != "completed" or (old and old.get("v", 0) >= FORMAT): continue
            if time.time() - t_start > BUDGET: skipped += 1; continue
            try:
                cache[g["id"]] = fetch_game(g, e, bo); new += 1
                OUT.parent.mkdir(exist_ok=True); OUT.write_text(json.dumps(cache, ensure_ascii=False))
            except Exception as ex: print("  game", g["id"], "failed:", ex); bad += 1
            time.sleep(0.3)
    OUT.parent.mkdir(exist_ok=True); OUT.write_text(json.dumps(cache, ensure_ascii=False))
    print("riot games: %d saved (%d new, %d failed)%s" % (len(cache), new, bad, (" | %d left for the next run" % skipped) if skipped else ""))

if __name__ == "__main__":
    try: main()
    except Exception as e: print("riot games fetch failed (keeping what is saved):", repr(e), file=sys.stderr)
