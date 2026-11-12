#!/usr/bin/env python3
"""Render the weekly Romain Trading macro recap visual.

Usage: python3 render_recap.py recap_data.json brand.css logo.txt out.png
"""
import datetime, html, json, sys
from playwright.sync_api import sync_playwright

data_path, css_path, logo_path, out_path = sys.argv[1:5]
d = json.load(open(data_path))
fonts = open(css_path).read()
logo = open(logo_path).read().strip()
e = html.escape

MONTHS = ['janvier', 'février', 'mars', 'avril', 'mai', 'juin', 'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre']
def fdate(s):
    dt = datetime.date.fromisoformat(s)
    return f"{dt.day} {MONTHS[dt.month - 1]} {dt.year}"
def fr(x, n=1):
    s = f"{x:+.{n}f}".replace('.', ',')
    return s.replace('-', '−')

reg = d['regime']
r20 = reg['20']
score = r20['score']; mx = r20['max']
pos = (score + mx) / (2 * mx) * 100

def chips(rows, cls):
    if not rows:
        return '<span class="chip muted">Aucune</span>'
    return ''.join(f'<span class="chip {cls}">{e(r["name"])}</span>' for r in rows)

fav = [a for a in d['assets'] if a['status'] == 'Favorisé']
neu = [a for a in d['assets'] if a['status'] == 'Neutre']
dfv = [a for a in d['assets'] if a['status'] == 'Défavorisé']

def sector_rows(rows, cls):
    if not rows:
        return '<div class="srow muted">Aucun secteur nettement concerné</div>'
    return ''.join(f'<div class="srow"><span>{e(r["name"])}</span><b class="{cls}">{e(r["symbol"])}</b></div>' for r in rows)

def names(rows):
    return ' · '.join(e(r['name']) for r in rows) if rows else 'Aucun'

perf = d['perf']
ext = max(abs(p['rel']) for p in perf) or 0.01
bars = ''
for p in perf:
    w = abs(p['rel']) / ext * 46
    side = 'left:50%' if p['rel'] >= 0 else 'right:50%'
    cls = 'up' if p['rel'] >= 0 else 'down'
    bars += (f'<div class="brow"><span class="bname">{e(p["symbol"])}</span><div class="btrack"><i class="{cls}" style="{side};width:{w:.1f}%"></i></div>'
             f'<span class="bval {cls}">{fr(p["rel"] * 100)} %</span></div>')

# Courbes base 100 sur 1 mois : 3 meilleurs et 3 moins bons secteurs + S&P 500
top = [p['symbol'] for p in perf[:3]]; bot = [p['symbol'] for p in perf[-3:]]
COL = {s: c for s, c in zip(top, ['#00E27F', '#5BE9A8', '#A7F3D0'])}
COL.update({s: c for s, c in zip(reversed(bot), ['#FF2D46', '#FF6B81', '#FCA5B4'])})
lines = {l['symbol']: l['pts'] for l in d['lines']}
W, Hc, ml, mr, mt, mb = 560, 410, 44, 62, 10, 24
allv = [p['v'] for s, pts in lines.items() for p in pts]
lo, hi = min(allv), max(allv); pad = (hi - lo) * 0.06 or 1; lo -= pad; hi += pad
n = max(len(v) for v in lines.values())
X = lambda i: ml + i * (W - ml - mr) / (n - 1)
Y = lambda v: mt + (hi - v) * (Hc - mt - mb) / (hi - lo)
svg = [f'<svg width="{W}" height="{Hc}" viewBox="0 0 {W} {Hc}">']
step = 5 if hi - lo > 12 else 2
import math
g = math.ceil(lo / step) * step
while g <= hi:
    svg.append(f'<line x1="{ml}" x2="{W - mr}" y1="{Y(g):.1f}" y2="{Y(g):.1f}" stroke="rgba(170,140,255,{0.45 if g == 100 else 0.13})" stroke-width="{1.5 if g == 100 else 1}"{" stroke-dasharray=\"6 5\"" if g == 100 else ""}/>')
    svg.append(f'<text x="{ml - 8}" y="{Y(g) + 6:.1f}" text-anchor="end" fill="#7C77A8" font-size="16">{g}</text>')
    g += step
def path(pts):
    return 'M' + ' L'.join(f'{X(i):.1f},{Y(p["v"]):.1f}' for i, p in enumerate(pts))
for s, pts in lines.items():
    if s in COL or s == 'SPY':
        continue
    svg.append(f'<path d="{path(pts)}" fill="none" stroke="rgba(167,139,250,.28)" stroke-width="2"/>')
svg.append(f'<path d="{path(lines["SPY"])}" fill="none" stroke="#F2F0FF" stroke-width="2.5" stroke-dasharray="7 6"/>')
ends = []
for s in top + bot:
    pts = lines[s]
    svg.append(f'<path d="{path(pts)}" fill="none" stroke="{COL[s]}" stroke-width="3.5" stroke-linejoin="round" stroke-linecap="round" style="filter:drop-shadow(0 0 6px {COL[s]}88)"/>')
    ends.append([Y(pts[-1]['v']), s, COL[s]])
ends.append([Y(lines['SPY'][-1]['v']), 'S&P', '#F2F0FF'])
ends.sort()
for i in range(1, len(ends)):
    if ends[i][0] - ends[i - 1][0] < 19: ends[i][0] = ends[i - 1][0] + 19
for y, s, c in ends:
    svg.append(f'<text x="{W - mr + 8}" y="{y + 6:.1f}" fill="{c}" font-size="17" font-weight="700">{e(s)}</text>')
svg.append('</svg>')
chart = ''.join(svg)

page = f"""<!doctype html><html lang="fr"><head><meta charset="utf-8"><style>
{fonts}
*{{box-sizing:border-box;margin:0;padding:0}}
body{{width:1080px;height:1920px;overflow:hidden;font-family:'RT Space Grotesk',sans-serif;color:#F2F0FF;
 background:linear-gradient(180deg,rgba(124,58,237,.20) 0%,rgba(124,58,237,0) 260px),linear-gradient(0deg,rgba(124,58,237,.20) 0%,rgba(124,58,237,0) 260px),
 linear-gradient(90deg,rgba(124,58,237,.16) 0%,rgba(124,58,237,0) 180px),linear-gradient(270deg,rgba(124,58,237,.16) 0%,rgba(124,58,237,0) 180px),#000;
 padding:68px 60px 44px;display:flex;flex-direction:column;gap:26px}}
.head{{display:flex;align-items:center;gap:28px}}
.logo{{width:132px;height:132px;border-radius:34px;border:3px solid rgba(170,140,255,.9);box-shadow:0 0 40px rgba(124,58,237,.85),0 0 10px rgba(160,130,255,.9)}}
.htxt{{display:flex;flex-direction:column;gap:10px}}
.handle{{align-self:flex-start;font-family:'RT Poppins';font-weight:500;font-size:22px;padding:5px 18px;border-radius:40px;background:#00E27F;color:#05040F;box-shadow:0 0 18px rgba(0,226,127,.55)}}
h1{{font-family:'RT Nunito';font-weight:900;font-size:68px;line-height:1;letter-spacing:.01em;background:linear-gradient(180deg,#FFFFFF 0%,#DCE6FF 40%,#8EA8E8 60%,#EEF3FF 100%);-webkit-background-clip:text;background-clip:text;color:transparent;filter:drop-shadow(0 0 18px rgba(120,150,255,.5))}}
.sub{{font-size:24px;color:#A9A3D6}}
.glow{{height:3px;border-radius:2px;background:linear-gradient(90deg,rgba(127,178,255,0),#9FC2FF 50%,rgba(127,178,255,0));box-shadow:0 0 14px rgba(110,139,255,.9)}}
.card{{background:rgba(20,12,60,.55);border:2px solid rgba(170,140,255,.55);border-radius:28px;box-shadow:0 0 26px rgba(124,58,237,.38),inset 0 0 18px rgba(124,58,237,.18);padding:22px 28px}}
.lbl{{font-size:19px;font-weight:700;letter-spacing:.12em;color:#A9A3D6;text-transform:uppercase;margin-bottom:12px;display:flex;align-items:center;gap:12px}}
.lbl::before{{content:'';width:26px;height:4px;border-radius:2px;background:#00E27F;box-shadow:0 0 10px rgba(0,226,127,.8)}}
.regime{{display:flex;align-items:center;gap:30px}}
.rpill{{font-family:'RT Poppins';font-weight:700;font-size:40px;padding:10px 28px;border-radius:60px;background:rgba(167,139,250,.18);box-shadow:inset 0 0 0 2px rgba(196,181,253,.75),0 0 26px rgba(124,58,237,.55);white-space:nowrap}}
.gauge{{flex:1;display:flex;flex-direction:column;gap:8px}}
.gbar{{position:relative;height:18px;border-radius:9px;background:linear-gradient(90deg,#FF2D46 0%,rgba(255,45,70,.35) 30%,#000 43%,#000 57%,rgba(0,226,127,.35) 70%,#00E27F 100%);box-shadow:inset 0 0 0 1.5px rgba(170,140,255,.45)}}
.gpin{{position:absolute;top:-12px;width:6px;height:42px;border-radius:3px;background:#fff;box-shadow:0 0 14px rgba(255,255,255,.9);transform:translateX(-50%)}}
.gleg{{display:flex;justify-content:space-between;font-size:18px;color:#A9A3D6}}
.hz{{font-size:19px;color:#A9A3D6;margin-top:10px}}
.hz b{{color:#F2F0FF;font-weight:500}}
.grid3{{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}}
.col h3{{font-size:20px;font-weight:700;margin-bottom:10px}}
.col.mid{{text-align:center}} .col.mid .chips{{justify-content:center}}
.chips{{display:flex;flex-wrap:wrap;gap:8px}}
.chip{{font-size:19px;padding:6px 14px;border-radius:30px;background:rgba(242,240,255,.07)}}
.chip.fav{{background:rgba(0,226,127,.14);color:#00E27F;box-shadow:inset 0 0 0 1.5px rgba(0,226,127,.45)}}
.chip.def{{background:rgba(255,45,70,.14);color:#FF5A6E;box-shadow:inset 0 0 0 1.5px rgba(255,45,70,.45)}}
.chip.neu{{background:rgba(167,139,250,.16);color:#DCD3FF;box-shadow:inset 0 0 0 1.5px rgba(167,139,250,.45)}}
.chip.muted{{color:#7C77A8}}
.two{{display:grid;grid-template-columns:1fr 1fr;gap:16px}}
.srow{{display:flex;justify-content:space-between;font-size:21px;padding:5px 0;border-bottom:1px solid rgba(170,140,255,.15)}}
.srow:last-child{{border-bottom:0}}
.muted{{color:#7C77A8}}
.up{{color:#00E27F}} .down{{color:#FF2D46}}
.rot{{display:grid;grid-template-columns:auto 1fr;gap:8px 18px;font-size:21px;align-items:baseline}}
.rot b{{font-weight:700;white-space:nowrap}}
.brow{{display:grid;grid-template-columns:62px 1fr 84px;align-items:center;gap:8px;height:36px}}
.bname{{font-size:18px;font-weight:700;color:#CFCAF0;white-space:nowrap}}
.btrack{{position:relative;height:16px}}
.btrack::after{{content:'';position:absolute;left:50%;top:-4px;width:2px;height:24px;background:rgba(242,240,255,.35)}}
.btrack i{{position:absolute;top:0;height:16px;border-radius:4px}}
.btrack i.up{{background:linear-gradient(90deg,#00B865,#00E27F);box-shadow:0 0 10px rgba(0,226,127,.45)}}
.btrack i.down{{background:linear-gradient(90deg,#FF2D46,#C0122A);box-shadow:0 0 10px rgba(255,45,70,.45)}}
.bval{{font-family:'RT Poppins';font-weight:700;font-size:18px;text-align:right}}
.perfgrid{{display:grid;grid-template-columns:560px 1fr;gap:18px;align-items:start}}
.chartnote{{font-size:16px;color:#7C77A8;margin-top:4px}}
.foot{{margin-top:auto;display:flex;justify-content:space-between;font-size:16px;color:#7C77A8}}
</style></head><body>
<div class="head"><img class="logo" src="{logo}"><div class="htxt"><span class="handle">Romain Trading · RomaiNxTRADES</span><h1>RÉCAP MACRO</h1><span class="sub">Données à la clôture du {fdate(d['asof'])}</span></div></div>
<div class="glow"></div>
<div class="card"><div class="lbl">Régime de marché · 1 mois</div>
 <div class="regime"><span class="rpill">{e(r20['label'])}</span>
  <div class="gauge"><div class="gbar"><span class="gpin" style="left:{pos:.1f}%"></span></div><div class="gleg"><span>Risk Off</span><span>Risk On</span></div></div></div>
 <div class="hz">1 semaine : <b>{e(reg['5']['label'])}</b> · 3 mois : <b>{e(reg['60']['label'])}</b></div></div>
<div class="card"><div class="lbl">Où se positionner</div><div class="grid3">
 <div class="col"><h3 class="up">Favorisés</h3><div class="chips">{chips(fav, 'fav')}</div></div>
 <div class="col mid"><h3 style="color:#C4B5FD">Neutres</h3><div class="chips">{chips(neu, 'neu')}</div></div>
 <div class="col"><h3 class="down">Défavorisés</h3><div class="chips">{chips(dfv, 'def')}</div></div></div></div>
<div class="two">
 <div class="card"><div class="lbl">▲ Portés par la macro</div>{sector_rows(d['up'], 'up')}</div>
 <div class="card"><div class="lbl">▼ Pénalisés</div>{sector_rows(d['down'], 'down')}</div></div>
<div class="card"><div class="lbl">Rotation des secteurs</div><div class="rot">
 <b class="up">🏆 Leaders</b><span>{names(d['leaders'])}</span>
 <b style="color:#5BA8FF">🚀 Gagnent du terrain</b><span>{names(d['gaining'])}</span>
 <b class="down">🔻 Reculent</b><span>{names(d['losing'])}</span></div></div>
<div class="card"><div class="lbl">Secteurs · 1 mois</div><div class="perfgrid"><div>{chart}<div class="chartnote">Base 100 · S&amp;P 500 en pointillés</div></div><div><div class="chartnote" style="margin:0 0 6px">Écart vs S&amp;P 500</div>{bars}</div></div></div>
<div class="foot"><span>Contenu éducatif · ne constitue pas un conseil en investissement</span><span>Tableau de bord complet sur le Discord</span></div>
</body></html>"""

with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={'width': 1080, 'height': 1920}, device_scale_factor=1)
    pg.set_content(page, wait_until='load')
    pg.wait_for_timeout(300)
    over = pg.evaluate('document.body.scrollHeight')
    pg.screenshot(path=out_path, full_page=False)
    b.close()
print('rendered', out_path, 'content height', over)
