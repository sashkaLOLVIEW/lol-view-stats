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
<div style="position:absolute;left:0;right:0;bottom:0;height:{300*u}px;background:linear-gradient(to top,rgba(4,18,60,.97) 0%,rgba(8,32,96,.92) 45%,rgba(8,32,96,0) 100%)"></div>
<div style="position:absolute;left:0;right:0;bottom:{46*u}px;height:{118*u}px;display:flex;align-items:center;padding:0 {56*u}px;gap:{34*u}px;background:linear-gradient(90deg,#0b2f86,#1b57c9 60%,#0b2f86);border-top:{3*u}px solid rgba(255,255,255,.35);border-bottom:{3*u}px solid rgba(0,0,0,.25)">
<div style="flex:1;font-weight:900;font-size:{50*u}px;letter-spacing:.01em;line-height:1;white-space:nowrap;min-width:0;overflow:hidden">{a.headline}</div>
<div style="text-align:right;flex:none;white-space:nowrap;border-left:{3*u}px solid rgba(255,255,255,.45);padding-left:{30*u}px"><div style="font-weight:800;font-size:{44*u}px;line-height:1">{a.date}</div><div style="font-weight:600;font-size:{17*u}px;opacity:.85;margin-top:{8*u}px;letter-spacing:.04em">{a.sub}</div></div>
{f'<img src="{logo}" style="height:{92*u}px;margin-left:{6*u}px;flex:none">' if logo else ''}</div>
<div style="position:absolute;left:{56*u}px;bottom:{14*u}px;font-size:{15*u}px;letter-spacing:.14em;opacity:.7">LOL VIEW · FAN STATS</div></div></body></html>'''
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(viewport={'width': W, 'height': H}, device_scale_factor=1)
    pg.set_content(html); pg.wait_for_timeout(400); pg.screenshot(path=a.o); b.close()
print('wrote', a.o)
