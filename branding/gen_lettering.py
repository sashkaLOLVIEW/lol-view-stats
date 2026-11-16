import random
random.seed(7)
BARK='#6a4126'; BARK2='#8c5b34'; MOSS='#7b8a2c'
LEAF=['#e8641a','#f39a1f','#c8421a','#f2b83a','#d9731e','#b8432a']
W,H=860,300
defs={
 'p':(55,["M0,80 L0,215","M0,92 C12,76 52,74 54,110 C56,148 14,154 0,134"]),
 'r':(46,["M0,80 L0,150","M0,108 C6,86 28,76 46,84"]),
 'o':(56,["M28,76 C64,76 64,152 28,152 C-8,152 -8,76 28,76 Z"]),
 'h':(52,["M0,24 L0,150","M0,108 C10,80 50,78 52,110 L52,150"]),
 'u':(52,["M0,80 L0,118 C0,158 52,158 52,118","M52,80 L52,150"]),
 'b':(56,["M0,24 L0,150","M0,92 C12,76 52,74 54,110 C56,148 14,154 0,134"]),
 '.':(10,["M2,148 L3,149"]),
 'l':(6,["M0,24 L0,150"]),
}
word='prohub.lol'; gap=30; x=0; pos=[]
for ch in word:
    w,ps=defs[ch]; pos.append((ch,x,ps,w)); x+=w+(18 if ch=='.' else gap)
total=x-gap; shift=(W-total)/2
trunk=hi=vine=leaves=''
for ch,x0,ps,w in pos:
    sw=16 if ch!='.' else 24
    idx=pos.index((ch,x0,ps,w)); col=('#8a9a2e' if idx>=6 else None)
    trunk+=(f'<g stroke="{col}">' if col else '<g>')+f'<g transform="translate({x0+shift:.1f},0)">'+''.join(f'<path d="{d}" stroke-width="{sw}"/>' for d in ps)+'</g></g>'
    hi+=f'<g transform="translate({x0+shift-3:.1f},-2)">'+''.join(f'<path d="{d}" stroke-width="4"/>' for d in ps)+'</g>'
branches=["M20,180 C10,120 50,100 80,110 C100,116 110,90 140,86",
 "M18,215 C90,250 170,215 260,238 C360,262 440,225 540,248 C640,272 720,240 842,258",
 "M836,160 C800,192 770,150 740,180"]
for d in branches:
    trunk+=f'<path d="{d}" stroke-width="9"/>'; hi+=f'<g transform="translate(-1,-2)"><path d="{d}" stroke-width="2.5"/></g>'
for d in ["M10,262 C120,226 210,282 330,248 C450,214 500,280 620,244 C720,214 780,270 850,240",
          "M30,16 C100,40 160,4 250,24 C340,44 400,6 490,26 C580,46 650,8 740,28 C790,38 820,20 850,30"]:
    vine+=f'<path d="{d}" stroke-width="5"/>'
def leaf(cx,cy,s,rot,col):
    return (f'<g transform="translate({cx:.1f},{cy:.1f}) rotate({rot:.0f}) scale({s:.2f})"><path d="M0,-6 C5,-5 8,-1 8,3 C8,8 3,11 0,14 C-3,11 -8,8 -8,3 C-8,-1 -5,-5 0,-6 Z" fill="{col}"/>'
            '<path d="M0,-5 L0,12" stroke="#00000033" stroke-width="1" fill="none"/></g>')
for i in range(60):
    leaves+=leaf(random.uniform(20,W-20),random.choice([random.uniform(4,40),random.uniform(235,290),random.uniform(205,230)]),random.uniform(0.7,1.5),random.uniform(0,360),random.choice(LEAF))
for ch,x0,ps,w in pos:
    for _ in range(1):
        leaves+=leaf(x0+shift+random.uniform(-14,w+14),random.choice([random.uniform(10,40),random.uniform(160,200)]),random.uniform(0.9,1.6),random.uniform(0,360),random.choice(LEAF))
svg=f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">
<defs><filter id="w" x="-5%" y="-5%" width="110%" height="110%"><feTurbulence type="fractalNoise" baseFrequency="0.018" numOctaves="2" seed="4"/><feDisplacementMap in="SourceGraphic" scale="8"/></filter></defs>
<g filter="url(#w)" fill="none" stroke-linecap="round" stroke-linejoin="round">
<g stroke="{BARK}">{trunk}</g><g stroke="{BARK2}" opacity=".85">{hi}</g><g stroke="{MOSS}" opacity=".95">{vine}</g></g>
<g filter="url(#w)">{leaves}</g></svg>'''
open('prohub-lettering.svg','w').write(svg)
