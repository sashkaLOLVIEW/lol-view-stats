#!/usr/bin/env python3
"""Broadcast-style lower-third graphic. Usage:
  python3 social/card.py --team BLG --headline "BLG ADVANCE TO THE SEMIFINALS" \
     --date "NOV 6" --sub "QUARTERFINALS · DAY 3" [--photo pic.jpg] [--event WLDs] [--size 1600x900] -o out.png
Team logos come from the site's data (dist/index.html), event icons from config/event_icons.json."""
import argparse, base64, json, sys, pathlib
from playwright.sync_api import sync_playwright
R = pathlib.Path(__file__).resolve().parent.parent
ap = argparse.ArgumentParser()
ap.add_argument('--team'); ap.add_argument('--headline', required=True); ap.add_argument('--date', default=''); ap.add_argument('--sub', default='')
ap.add_argument('--photo'); ap.add_argument('--event', default='WLDs'); ap.add_argument('--size', default='1600x900'); ap.add_argument('-o', default='card.png')
a = ap.parse_args(); W, H = map(int, a.size.split('x'))
logo = ''
if a.team:
    s = (R / 'dist/index.html').read_text(encoding='utf-8'); i = s.index('var LOGOS'); k = s.index('{', s.index('=', i))
    logo = json.JSONDecoder().raw_decode(s[k:])[0].get(a.team, '')
ev = json.load(open(R / 'config/event_icons.json')).get(a.event, {}).get('d', '')
bg = ''
if a.photo:
    b = pathlib.Path(a.photo).read_bytes(); bg = 'data:image/%s;base64,%s' % (pathlib.Path(a.photo).suffix[1:].replace('jpg', 'jpeg'), base64.b64encode(b).decode())
u = H / 900
html = f'''<html><body style="margin:0"><div style="position:relative;width:{W}px;height:{H}px;overflow:hidden;font-family:'Helvetica Neue',Arial,'Liberation Sans',sans-serif;color:#fff;
background:{'url('+bg+') center/cover' if bg else 'radial-gradient(120% 90% at 50% 25%,#2a4f8f 0%,#10224a 55%,#070d1f 100%)'}">
<div style="position:absolute;left:{40*u}px;top:{34*u}px;display:flex;align-items:center;gap:{12*u}px">{f'<img src="{ev}" style="height:{44*u}px">' if ev else ''}</div>
<div style="position:absolute;left:0;right:0;bottom:0;height:{420*u}px;background:linear-gradient(to top,rgba(5,16,120,.55) 0%,rgba(30,70,200,.28) 60%,rgba(30,70,200,0) 100%)"></div>
<svg style="position:absolute;left:0;bottom:0" width="{W}" height="{300*u}" viewBox="0 0 1600 300" preserveAspectRatio="none">
<defs>
<linearGradient id="p" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#0b2bb8"/><stop offset=".35" stop-color="#0a1f95"/><stop offset="1" stop-color="#050d4c"/></linearGradient>
<radialGradient id="gl" cx=".5" cy=".5" r=".5"><stop offset="0" stop-color="#bcd8ff" stop-opacity=".95"/><stop offset=".35" stop-color="#4f8dff" stop-opacity=".5"/><stop offset="1" stop-color="#2a5cff" stop-opacity="0"/></radialGradient>
<linearGradient id="st" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#4a7dff" stop-opacity="0"/><stop offset=".5" stop-color="#6aa0ff" stop-opacity=".55"/><stop offset="1" stop-color="#4a7dff" stop-opacity="0"/></linearGradient>
</defs>
<path d="M0 62 C200 56 420 40 800 38 C1180 36 1400 54 1600 60 L1600 300 L0 300Z" fill="url(#p)"/>
<ellipse cx="800" cy="40" rx="620" ry="34" fill="url(#gl)" opacity=".85"/>
<path d="M0 62 C200 56 420 40 800 38 C1180 36 1400 54 1600 60" stroke="#8db8ff" stroke-width="2" fill="none" opacity=".75"/>
<path d="M-40 250 C300 170 700 214 1100 150 C1300 118 1500 120 1660 100" stroke="url(#st)" stroke-width="3" fill="none"/>
<path d="M-40 276 C360 206 760 250 1160 186 C1360 156 1520 158 1660 142" stroke="url(#st)" stroke-width="2" fill="none" opacity=".7"/>
<path d="M0 300 L0 240 C300 190 760 226 1200 170 L1600 150 L1600 300Z" fill="#0a2ab0" opacity=".28"/>
</svg>
<div style="position:absolute;left:0;right:0;bottom:{70*u}px;height:{130*u}px;display:flex;align-items:center;padding:0 {40*u}px;gap:{22*u}px;font-family:'DejaVu Sans Condensed','DejaVu Sans',sans-serif">
<div style="font-weight:900;font-size:{86*u}px;letter-spacing:.01em;line-height:1;white-space:nowrap;color:#e9e9ef;text-shadow:0 {4*u}px {16*u}px rgba(0,5,60,.6)">{a.headline}</div>
<div style="flex:none;white-space:nowrap;color:#f2f2f6;line-height:1"><div style="font-weight:800;font-size:{40*u}px">{a.date}</div><div style="font-weight:700;font-size:{20*u}px;margin-top:{8*u}px;opacity:.92">{a.sub}</div></div>
<div style="flex:1"></div>
{f'<img src="{logo}" style="height:{74*u}px;flex:none;filter:drop-shadow(0 0 {8*u}px rgba(120,180,255,.45))">' if logo else ''}</div>
<div style="position:absolute;left:{40*u}px;right:{40*u}px;bottom:{18*u}px;display:flex;justify-content:space-between;font-size:{13*u}px;letter-spacing:.12em;color:#cfd8ff;opacity:.75;font-weight:600"><span>LOL ESPORTS</span><span>OCTOBER – NOVEMBER</span><span>WORLDS 2026</span></div>
</div></body></html>'''
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(viewport={'width': W, 'height': H}, device_scale_factor=1)
    pg.set_content(html); pg.wait_for_timeout(400); pg.screenshot(path=a.o); b.close()
print('wrote', a.o)
