#!/usr/bin/env python3
"""Diagnostic: how does dpm.lol get summoner spells for an esports game? Fetches one match page and lists its data sources."""
import re, sys, json, requests
URL = "https://dpm.lol/esports/matches/139847-top-esports-vs-bilibili-gaming?game=1"
H = {"User-Agent": "Mozilla/5.0 (compatible; lol-view-stats probe)"}
r = requests.get(URL, headers=H, timeout=30); print("page:", r.status_code, len(r.text), "bytes")
t = r.text
print("next data:", bool(re.search(r"__NEXT_DATA__", t)), "| nuxt:", "__NUXT__" in t)
for m in sorted(set(re.findall(r"https?://[A-Za-z0-9._~:/?#\[\]@!$&'()*+,;=%-]+", t)))[:80]:
    if not re.search(r"\.(png|jpg|webp|svg|woff2?|css|ico)(\?|$)", m): print("url:", m[:200])
for m in re.finditer(r"[^\"\s]{0,60}[Ss]ummoner[^\"\s]{0,60}", t): print("summoner ref:", m.group(0)); 
srcs = re.findall(r'src="([^"]+\.js[^"]*)"', t)
print("scripts:", len(srcs))
seen = 0
for s in srcs[:40]:
    u = s if s.startswith("http") else "https://dpm.lol" + s
    try: js = requests.get(u, headers=H, timeout=30).text
    except Exception as e: print("  script failed", u, e); continue
    for m in re.finditer(r"https?://[A-Za-z0-9._/-]*(?:api|feed|lolesports|esports)[A-Za-z0-9._/{}$?=&-]*", js):
        print("  api-ish:", m.group(0)[:160]); seen += 1
        if seen > 60: break
    for m in re.finditer(r"[^\"'`]{0,50}(?:summoner|spell)[A-Za-z]{0,20}[^\"'`]{0,40}", js, re.I):
        print("  js hint:", m.group(0)[:140]); seen += 1
        if seen > 120: break
