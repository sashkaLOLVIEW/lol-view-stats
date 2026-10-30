#!/usr/bin/env python3
"""Diagnostic: why is a player's trinket missing? Prints Riot's raw participant record and item timeline for the junglers of one match.

    python tools/probe_items.py BLG TES        (team codes of the match, any order; default BLG TES)
"""
import json, sys, time, datetime as dt
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import fetch_items as F

want = {c.upper() for c in (sys.argv[1:3] or ["BLG", "TES"])}
ms = F.finished_matches()
hit = [e for e in ms.values() if {t["code"].upper() for t in e["match"]["teams"]} == want]
print("matches found for", sorted(want), ":", len(hit))
for e in hit:
    games = F.get(F.GW + "/getEventDetails", hl="en-US", id=e["match"]["id"])["data"]["event"]["match"]["games"]
    for g in games:
        if g.get("state") != "completed": continue
        gid = g["id"]; print("\n===== game", g["number"], gid)
        w0 = F.get(F.FEED + "/window/" + gid); md = w0["gameMetadata"]; t0 = F.iso(w0["frames"][0]["rfc460Timestamp"])
        wend = F.get(F.FEED + "/window/" + gid, startingTime=F.fmt(F.floor10(t0 + dt.timedelta(hours=3))))
        tend = F.iso(wend["frames"][-1]["rfc460Timestamp"]); mins = (tend - t0).total_seconds() / 60
        print("start", F.fmt(t0), "end", F.fmt(tend), "length %.1f min" % mins, "| patch", md.get("patchVersion"))
        jung = {}
        for side in ("blue", "red"):
            for pm in md[side + "TeamMetadata"]["participantMetadata"]:
                if pm["role"] == "jungle": jung[pm["participantId"]] = (side, pm.get("summonerName"), pm.get("championId"))
        print("junglers:", jung)
        # full raw record at the end of the game
        det = F.get(F.FEED + "/details/" + gid, startingTime=F.fmt(F.floor10(tend - dt.timedelta(seconds=30))))
        fr = det.get("frames") or []; print("frames in the final call:", len(fr), "| last frame time", fr[-1].get("rfc460Timestamp") if fr else None)
        for pid, (side, name, champ) in jung.items():
            rec = next((p for p in fr[-1]["participants"] if p["participantId"] == pid), None)
            print("\n--- final frame, raw record:", side, name, champ); print(json.dumps(rec)[:1500])
            print("--- items in each of the last frames:", [ [p.get("items") for p in f["participants"] if p["participantId"] == pid][0] for f in fr ])
        # item timeline, every 2 minutes
        print("\n--- item timeline (minute: items) ---")
        rows = {pid: [] for pid in jung}
        m = 2
        while m < mins:
            t = t0 + dt.timedelta(minutes=m)
            try: d = F.get(F.FEED + "/details/" + gid, startingTime=F.fmt(F.floor10(t))).get("frames") or []
            except Exception as ex: print("  minute", m, "failed:", ex); m += 2; continue
            if d:
                for pid in jung:
                    p = next((q for q in d[0]["participants"] if q["participantId"] == pid), {})
                    rows[pid].append((m, p.get("items")))
            m += 2; time.sleep(0.2)
        for pid, (side, name, champ) in jung.items():
            print("\n%s %s (%s)" % (side, name, champ))
            for mm, it in rows[pid]: print("  %2d min: %s" % (mm, it))
