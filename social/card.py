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
<div style="position:absolute;left:0;right:0;bottom:0;height:{330*u}px;background:linear-gradient(to top,rgba(3,12,48,.95) 0%,rgba(6,24,84,.7) 50%,rgba(6,24,84,0) 100%)"></div>
<svg style="position:absolute;left:0;bottom:0" width="{W}" height="{340*u}" viewBox="0 0 1600 250" preserveAspectRatio="none">
<defs>
<linearGradient id="g1" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#061a5c"/><stop offset=".5" stop-color="#0d3bb0"/><stop offset="1" stop-color="#0a2a86"/></linearGradient>
<linearGradient id="g2" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#2f7bff" stop-opacity=".9"/><stop offset="1" stop-color="#0b3ac0" stop-opacity=".2"/></linearGradient>
<linearGradient id="g3" x1="0" y1="1" x2="1" y2="0"><stop offset="0" stop-color="#03103f"/><stop offset="1" stop-color="#0b2d94"/></linearGradient>
<linearGradient id="g4" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#5aa2ff" stop-opacity=".75"/><stop offset="1" stop-color="#5aa2ff" stop-opacity="0"/></linearGradient>
</defs>
<path d="M0 118 C260 92 520 150 820 118 C1120 86 1380 140 1600 104 L1600 250 L0 250Z" fill="url(#g3)" opacity=".9"/>
<path d="M0 150 C300 120 560 176 880 142 C1160 112 1400 160 1600 132 L1600 250 L0 250Z" fill="url(#g1)"/>
<path d="M0 150 C300 120 560 176 880 142 C1160 112 1400 160 1600 132 L1600 150 C1400 178 1160 130 880 160 C560 196 300 138 0 168Z" fill="url(#g4)" opacity=".5"/>
<path d="M-20 196 C220 168 470 218 760 186 C1060 152 1330 212 1620 172 L1620 250 L-20 250Z" fill="#0a2480" opacity=".85"/>
<path d="M-20 214 C240 190 520 236 820 206 C1100 178 1360 228 1620 196 L1620 250 L-20 250Z" fill="#061a5c"/>
<path d="M1010 250 L1090 118 L1180 118 L1100 250Z" fill="#3c8bff" opacity=".22"/>
<path d="M1150 250 L1200 150 L1230 150 L1180 250Z" fill="#8fc1ff" opacity=".25"/>
<path d="M0 150 L520 150 L470 250 L0 250Z" fill="url(#g2)" opacity=".35"/>
<path d="M0 148 C300 118 560 174 880 140 C1160 110 1400 158 1600 130" stroke="#9cc8ff" stroke-width="2.5" fill="none" opacity=".8"/>
</svg>
<div style="position:absolute;left:0;right:0;bottom:{40*u}px;height:{130*u}px;display:flex;align-items:center;padding:0 {64*u}px;gap:{34*u}px">
<div style="flex:1;font-weight:900;font-size:{54*u}px;letter-spacing:.01em;line-height:1;white-space:nowrap;min-width:0;text-shadow:0 {3*u}px {14*u}px rgba(0,10,50,.55)">{a.headline}</div>
<div style="text-align:right;flex:none;white-space:nowrap;border-left:{3*u}px solid rgba(255,255,255,.5);padding-left:{30*u}px"><div style="font-weight:800;font-size:{44*u}px;line-height:1">{a.date}</div><div style="font-weight:600;font-size:{17*u}px;opacity:.9;margin-top:{8*u}px;letter-spacing:.04em">{a.sub}</div></div>
{f'<img src="{logo}" style="height:{92*u}px;margin-left:{6*u}px;flex:none;filter:drop-shadow(0 0 {10*u}px rgba(120,180,255,.5))">' if logo else ''}</div>
<div style="position:absolute;left:{56*u}px;bottom:{14*u}px;font-size:{15*u}px;letter-spacing:.14em;opacity:.7">LOL VIEW · FAN STATS</div></div></body></html>'''
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(viewport={'width': W, 'height': H}, device_scale_factor=1)
    pg.set_content(html); pg.wait_for_timeout(400); pg.screenshot(path=a.o); b.close()
print('wrote', a.o)
