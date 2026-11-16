#!/usr/bin/env python3
"""Render the weekly Romain Trading "Market Direction" visual (1600x900, format du post du 12/11).

Usage: python3 render_md.py map.json brand.css logo.txt out.png
map.json: {"IXIC": fmp_json, "GSPC": fmp_json, "EXSA_D": av_daily_csv, "EXSA_W": av_weekly_csv,
           "CAC_D": av_daily_csv, "CAC_W": av_weekly_csv}
Filtre façon Minervini / Qullamaggie : prix face aux MME 8 et 21, puis SMA 50 et SMA 200 ; FTD (O'Neil) sur les indices US.
"""
import csv, datetime, html, io, json, sys
from playwright.sync_api import sync_playwright

mp_path, css_path, logo_path, out_path = sys.argv[1:5]
mp = json.load(open(mp_path))
fonts = open(css_path).read()
logo = open(logo_path).read().strip()
e = html.escape
now = datetime.datetime.now(datetime.timezone.utc)
# Barre du jour exclue tant que la séance US n'est pas close (21h15 UTC)
CUTOFF = now.date().isoformat() if now.hour * 60 + now.minute < 21 * 60 + 15 else '9999'
NBARS = 60


def unwrap(text):
    try:
        d = json.loads(text)
    except Exception:
        return text
    if isinstance(d, dict):
        for k in ('result', 'sample_data'):
            if isinstance(d.get(k), str):
                return unwrap(d[k])
    return d


def load(path):
    d = unwrap(open(path).read())
    rows = []
    if isinstance(d, list):
        for r in d:
            rows.append((str(r['date'])[:10], float(r['open']), float(r['high']), float(r['low']), float(r['close']), float(r.get('volume') or 0)))
    else:
        for r in csv.DictReader(io.StringIO(d.strip().replace('\r', ''))):
            rows.append((r['timestamp'][:10], float(r['open']), float(r['high']), float(r['low']), float(r['close']), float(r.get('volume') or 0)))
    rows = sorted({r[0]: r for r in rows if r[0] < CUTOFF}.values())
    if len(rows) < 60:
        sys.exit(f'{path}: only {len(rows)} rows')
    return rows


def ema(vals, n):
    k = 2 / (n + 1); out = []; m = None
    for i, v in enumerate(vals):
        if i < n - 1:
            out.append(None); continue
        m = sum(vals[:n]) / n if i == n - 1 else v * k + m * (1 - k)
        out.append(m)
    return out


def sma(vals, n):
    return [None if i < n - 1 else sum(vals[i - n + 1:i + 1]) / n for i in range(len(vals))]


def ftd(rows):
    """Dernier Follow-Through Day valide : après le plus bas des 25 dernières séances, à partir du 4e jour de rebond,
    hausse >= 1,25 % avec volume supérieur à la veille, et plus bas non enfoncé depuis."""
    win = rows[-25:]
    li = min(range(len(win)), key=lambda i: win[i][3])
    low = win[li][3]
    for j in range(li + 3, len(win)):
        if min(r[3] for r in win[li + 1:j + 1]) < low:
            return None
        chg = win[j][4] / win[j - 1][4] - 1
        if chg >= 0.0125 and win[j][5] > win[j - 1][5] > 0:
            if min(r[3] for r in win[j:]) < low:
                return None
            return dict(date=win[j][0], chg=chg * 100, low=low)
    return None


def analyse(name, short, rows, weekly=None, points=True):
    c = [r[4] for r in rows]
    e8, e21, s50 = ema(c, 8), ema(c, 21), sma(c, 50)
    if weekly:  # SMA 200 jours ≈ SMA 40 semaines (le quotidien gratuit se limite à 100 séances)
        wc = [r[4] for r in weekly]; w40 = sma(wc, 40); wd = [r[0] for r in weekly]
        s200 = [w40[max([i for i, d in enumerate(wd) if d <= r[0]] or [0])] for r in rows]
        hi52 = max(r[2] for r in weekly[-52:])
        ath = max(r[2] for r in weekly)
    else:
        s200 = sma(c, 200); hi52 = max(r[2] for r in rows[-252:]); ath = None
    last = c[-1]
    ok = dict(e8=last > e8[-1], e21=last > e21[-1], cross=e8[-1] > e21[-1], s50=last > s50[-1], s200=s200[-1] is not None and last > s200[-1])
    score = sum(ok.values())
    side = ok['e21']; streak = 0
    for i in range(len(c) - 1, -1, -1):
        if e21[i] is None or (c[i] > e21[i]) != side: break
        streak += 1
    return dict(name=name, short=short, rows=rows[-NBARS:], e8=e8[-NBARS:], e21=e21[-NBARS:], s50=s50[-NBARS:], s200=s200[-NBARS:],
                last=last, date=rows[-1][0], ok=ok, score=score, streak=streak, points=points,
                lv=dict(e8=e8[-1], e21=e21[-1], s50=s50[-1], s200=s200[-1]),
                near_high=last >= hi52 * 0.985, at_ath=bool(ath) and last >= ath * 0.985,
                low20=min(r[3] for r in rows[-20:]), hi20=max(r[2] for r in rows[-20:]),
                ftd=ftd(rows) if points else None)


MONTHS = ['janv.', 'févr.', 'mars', 'avr.', 'mai', 'juin', 'juil.', 'août', 'sept.', 'oct.', 'nov.', 'déc.']
def fdate(s, year=True):
    dt = datetime.date.fromisoformat(s)
    return f"{dt.day} {MONTHS[dt.month - 1]}" + (f" {dt.year}" if year else '')
def dm(s):
    dt = datetime.date.fromisoformat(s); return f"{dt.day}/{dt.month}"
def num(x):
    return f"{x:,.0f}".replace(',', ' ')
def pc(x):
    return f"{abs(x):.1f}".replace('.', ',') + ' %'

LBL = dict(e8='MME 8', e21='MME 21', s50='SMA 50', s200='SMA 200')


def chip(a):
    """Petite étiquette sur le graphique, comme sur les captures TradingView."""
    if a['near_high']:
        return 'up', 'plus haut'
    mas = [k for k in ('e21', 's50', 's200')]
    above = [k for k in mas if a['ok'][k]]
    if len(above) == 3:
        return 'up', '› 3 MM'
    first_lost = next(k for k in mas if not a['ok'][k])
    return 'down', '‹ ' + LBL[first_lost]


def describe(a):
    """Une puce par indice."""
    ok = a['ok']
    if a['at_ath']:
        return 'up', f"{a['name']} au plus haut historique"
    if a['near_high']:
        return 'up', f"{a['name']} au plus haut sur 1 an"
    lost = [LBL[k] for k in ('e21', 's50', 's200') if not ok[k]]
    if not lost:
        txt = f"{a['name']} au-dessus de ses 3 moyennes"
        return ('up', txt) if ok['e8'] else ('warn', txt + ', sous sa MME 8')
    if len(lost) == 1:
        return 'down', f"{a['name']} sous sa {lost[0]}"
    return 'down', f"{a['name']} sous sa " + ', sa '.join(lost[:-1]) + f" et sa {lost[-1]}"


def regime(items):
    sc = sum(a['score'] for a in items) / len(items)
    f = [a['ftd'] for a in items if a['ftd']]
    if sc >= 4:
        return dict(cls='up', badge='OK POUR TRADER', expo='80-100 %' if sc >= 4.5 else '60-80 %',
                    tag='Uptrend confirmé' if sc >= 4.5 else 'Uptrend', act='Breakouts tradables en taille normale')
    if sc >= 3:
        return dict(cls='neu', badge='SÉLECTIF', expo='40-60 %', tag='Sous pression', act='Seulement les meilleurs setups, taille réduite')
    if sc >= 2 or f:
        return dict(cls='warn', badge='PRUDENCE', expo='20-40 %', tag='Petites positions', act='Petites positions, stops serrés')
    return dict(cls='down', badge='DÉFENSIF', expo='0-20 %', tag='Hors marché', act='Pas de nouvelles positions, attendre la reprise de la MME 21')


def bullets(items, rg):
    out = [describe(a) for a in items]
    f = next((a for a in items if a['ftd']), None)
    if rg['cls'] == 'up':
        out.append(('up', rg['act']))
        w = min(items, key=lambda a: a['last'] / a['lv']['e21'])  # le plus proche de sa MME 21
        if w['points']:
            out.append(('warn', f"Vigilance si le {w['short']} clôture sous {num(w['lv']['e21'])}"))
        else:
            out.append(('warn', f"Vigilance sous la MME 21 du {w['short']} (−{pc((w['last'] / w['lv']['e21'] - 1) * 100)})"))
        return out
    if f:
        out.append(('warn', f"FTD {f['short']} le {dm(f['ftd']['date'])} : reprise fragile"))
    else:
        out.append(('warn' if rg['cls'] != 'down' else 'down', rg['act']))
    a = f or max(items, key=lambda a: a['last'] / a['lv']['e21'])
    conf = max(a['lv']['e21'], a['last']) if a['last'] < a['lv']['e21'] else a['hi20']
    inval = a['ftd']['low'] if a['ftd'] else a['low20']
    if a['points']:
        out.append(('warn', f"Confirmation › {num(conf)} · invalidation ‹ {num(inval)}"))
    else:
        out.append(('warn', f"Confirmation : clôture au-dessus de la MME 21 du {a['short']}"))
    return out


def chart(a, W=300, H=230):
    ml, mr, mt, mb = 4, 50, 34, 8
    rows = a['rows']; n = len(rows)
    vals = [v for r in rows for v in (r[2], r[3])] + [v for k in ('e8', 'e21', 's50') for v in a[k] if v]
    s200v = [v for v in a['s200'] if v]
    lo, hi = min(vals), max(vals)
    if s200v and min(s200v) > lo - (hi - lo) * 0.5:
        lo = min(lo, min(s200v))
    pad = (hi - lo) * 0.05; lo -= pad; hi += pad
    X = lambda i: ml + (i + 0.5) * (W - ml - mr) / n
    Y = lambda v: mt + (hi - v) * (H - mt - mb) / (hi - lo)
    bw = (W - ml - mr) / n * 0.6
    cid = f"c{abs(hash(a['name']))}"
    s = [f'<svg width="{W}" height="{H}" viewBox="0 0 {W} {H}"><defs><clipPath id="{cid}"><rect x="0" y="0" width="{W - mr}" height="{H}"/></clipPath></defs>']
    for k in range(1, 5):
        y = mt + k * (H - mt - mb) / 5
        s.append(f'<line x1="0" x2="{W - mr}" y1="{y:.1f}" y2="{y:.1f}" stroke="rgba(170,140,255,.08)"/>')
    s.append(f'<line x1="{W - mr}" x2="{W - mr}" y1="0" y2="{H}" stroke="rgba(170,140,255,.18)"/>')
    s.append(f'<g clip-path="url(#{cid})">')
    def line(key, col, w, dash=''):
        pts = [(X(i), Y(v)) for i, v in enumerate(a[key]) if v is not None]
        if len(pts) > 1:
            s.append(f'<path d="M' + ' L'.join(f'{x:.1f},{y:.1f}' for x, y in pts) + f'" fill="none" stroke="{col}" stroke-width="{w}"{dash} stroke-linejoin="round"/>')
    line('s200', '#4F46E5', 1.8)
    line('s50', '#8E89BC', 1.4)
    line('e21', '#FFFFFF', 1.6)
    line('e8', '#5BE9A8', 1.4)
    for i, r in enumerate(rows):
        o, h, l, c = r[1:5]
        up = c >= o; col = '#F2F0FF' if up else '#8B5CF6'
        s.append(f'<line x1="{X(i):.1f}" x2="{X(i):.1f}" y1="{Y(h):.1f}" y2="{Y(l):.1f}" stroke="{col}" stroke-width="1"/>')
        y0, y1 = sorted((Y(o), Y(c)))
        s.append(f'<rect x="{X(i) - bw / 2:.1f}" y="{y0:.1f}" width="{bw:.1f}" height="{max(y1 - y0, 1):.1f}" fill="{col}"/>')
    s.append('</g>')
    tags = [[Y(a['last']), num(a['last']) if a['points'] else f"{a['last']:.2f}".replace('.', ','), '#05040F', '#00E27F' if a['ok']['e8'] else '#FF2D46']]
    for key, col in (('e21', '#FFFFFF'), ('s50', '#8E89BC'), ('s200', '#4F46E5')):
        v = a['lv'][key]
        if v and lo <= v <= hi:
            tags.append([Y(v), {'e21': '21', 's50': '50', 's200': '200'}[key], '#05040F' if key in ('e21', 's50') else '#F2F0FF', col])
    tags.sort()
    for i in range(1, len(tags)):
        if tags[i][0] - tags[i - 1][0] < 17: tags[i][0] = tags[i - 1][0] + 17
    shift = max(0, tags[-1][0] - (H - 10))
    for y, t, fg, bg in tags:
        y -= shift
        s.append(f'<rect x="{W - mr + 3}" y="{y - 8:.1f}" width="{mr - 5}" height="16" rx="3" fill="{bg}"/>'
                 f'<text x="{W - mr / 2 + 1}" y="{y + 4:.1f}" text-anchor="middle" fill="{fg}" font-size="11" font-weight="700">{t}</text>')
    s.append('</svg>')
    cls, txt = chip(a)
    return f'<div class="ch">{"".join(s)}<span class="cl"><b>{e(a["name"])}</b><i class="{cls}">{e(txt)}</i></span></div>'


def panel(title, items):
    rg = regime(items)
    bl = ''.join(f'<li class="{c}">{e(t)}</li>' for c, t in bullets(items, rg))
    return f"""<div class="panel"><div class="ph"><h2>{title}</h2><span class="badge {rg['cls']}">{rg['badge']}</span></div>
<div class="charts">{''.join(chart(a) for a in items)}</div>
<ul>{bl}</ul>
<div class="expo {rg['cls']}"><b>Exposition {rg['expo']}</b><span>{rg['tag']}</span></div></div>"""


us = [analyse('Nasdaq', 'Nasdaq', load(mp['IXIC'])), analyse('S&P 500', 'S&P 500', load(mp['GSPC']))]
eu = [analyse('Stoxx 600', 'Stoxx 600', load(mp['EXSA_D']), load(mp['EXSA_W']), points=False),
      analyse('CAC 40', 'CAC', load(mp['CAC_D']), load(mp['CAC_W']), points=False)]
asof = max(a['date'] for a in us + eu)
for a in us + eu:
    if (datetime.date.fromisoformat(asof) - datetime.date.fromisoformat(a['date'])).days > 5:
        sys.exit(f"{a['name']}: data stale ({a['date']})")

page = f"""<!doctype html><html lang="fr"><head><meta charset="utf-8"><style>
{fonts}
*{{box-sizing:border-box;margin:0;padding:0}}
body{{width:1600px;height:900px;overflow:hidden;font-family:'RT Poppins',sans-serif;color:#F2F0FF;
 background:radial-gradient(ellipse 900px 500px at 0% 0%,rgba(124,58,237,.30),rgba(124,58,237,0)),radial-gradient(ellipse 900px 500px at 100% 100%,rgba(124,58,237,.22),rgba(124,58,237,0)),#07051A;
 padding:38px 64px 22px;display:flex;flex-direction:column}}
.head{{display:flex;align-items:center;gap:28px}}
.logo{{width:106px;height:106px;border-radius:24px;border:2px solid rgba(170,140,255,.9);box-shadow:0 0 30px rgba(124,58,237,.7)}}
.ht{{display:flex;flex-direction:column;gap:8px;flex:1}}
.handle{{align-self:flex-start;font-weight:500;font-size:20px;padding:3px 16px;border-radius:30px;background:#00E27F;color:#05040F;box-shadow:0 0 16px rgba(0,226,127,.5)}}
h1{{font-family:'RT Nunito';font-weight:900;font-size:56px;line-height:1;background:linear-gradient(180deg,#FFFFFF 0%,#DCE6FF 45%,#8EA8E8 65%,#EEF3FF 100%);-webkit-background-clip:text;background-clip:text;color:transparent;filter:drop-shadow(0 0 14px rgba(120,150,255,.45))}}
.hr{{text-align:right;display:flex;flex-direction:column;gap:6px}}
.hr small{{font-size:22px;color:#A9A3D6}}
.hr b{{font-family:'RT Nunito';font-weight:900;font-size:40px;background:linear-gradient(180deg,#FFFFFF 0%,#DCE6FF 45%,#8EA8E8 65%,#EEF3FF 100%);-webkit-background-clip:text;background-clip:text;color:transparent}}
.glow{{height:2px;margin:16px 0 26px;background:linear-gradient(90deg,rgba(127,178,255,0),#9FC2FF 50%,rgba(127,178,255,0));box-shadow:0 0 12px rgba(110,139,255,.8)}}
.cols{{display:grid;grid-template-columns:1fr 1fr;gap:64px}}
.panel{{background:rgba(24,14,70,.45);border:2px solid rgba(170,140,255,.45);border-radius:26px;box-shadow:0 0 24px rgba(124,58,237,.3),inset 0 0 16px rgba(124,58,237,.12);padding:24px 30px 28px;display:flex;flex-direction:column;gap:16px}}
.ph{{display:flex;justify-content:space-between;align-items:center}}
h2{{font-family:'RT Nunito';font-weight:900;font-size:32px;letter-spacing:.01em}}
.badge{{font-weight:700;font-size:19px;padding:5px 16px;border-radius:30px}}
.charts{{display:grid;grid-template-columns:1fr 1fr;gap:12px}}
.ch{{position:relative;border-radius:14px;overflow:hidden;background:#0B0A14;border:1.5px solid rgba(170,140,255,.35);height:234px}}
.ch svg{{display:block;margin:2px 0 0 2px}}
.cl{{position:absolute;top:10px;left:10px;display:flex;align-items:center;gap:8px;padding:3px 12px;border-radius:20px;background:rgba(7,5,26,.85);border:1.5px solid rgba(170,140,255,.6);font-size:17px}}
.cl b{{font-weight:500}} .cl i{{font-style:normal;font-size:14px}}
.cl i.up{{color:#00E27F}} .cl i.down{{color:#FF5A6E}}
ul{{list-style:none;display:flex;flex-direction:column;gap:8px;margin:4px 0 2px}}
li{{font-size:23px;display:flex;align-items:center;gap:16px;line-height:1.25}}
li::before{{content:'';flex:none;width:12px;height:12px;border-radius:50%}}
li.up::before{{background:#00E27F;box-shadow:0 0 10px #00E27F}}
li.down::before{{background:#FF2D46;box-shadow:0 0 10px #FF2D46}}
li.warn::before{{background:#FFC24B;box-shadow:0 0 10px #FFC24B}}
li.neu::before{{background:#A78BFA;box-shadow:0 0 10px #A78BFA}}
.expo{{margin-top:auto;display:flex;justify-content:space-between;align-items:center;border-radius:16px;padding:16px 24px}}
.expo b{{font-weight:700;font-size:28px}} .expo span{{font-size:20px}}
.up.badge,.expo.up{{background:rgba(0,226,127,.12);color:#00E27F;box-shadow:inset 0 0 0 2px rgba(0,226,127,.55),0 0 16px rgba(0,226,127,.18)}}
.warn.badge,.expo.warn{{background:rgba(255,194,75,.12);color:#FFC24B;box-shadow:inset 0 0 0 2px rgba(255,194,75,.55),0 0 16px rgba(255,194,75,.15)}}
.down.badge,.expo.down{{background:rgba(255,45,70,.12);color:#FF5A6E;box-shadow:inset 0 0 0 2px rgba(255,45,70,.55),0 0 16px rgba(255,45,70,.18)}}
.neu.badge,.expo.neu{{background:rgba(167,139,250,.16);color:#DCD3FF;box-shadow:inset 0 0 0 2px rgba(196,181,253,.6),0 0 16px rgba(124,58,237,.3)}}
.foot{{margin-top:auto;display:flex;justify-content:space-between;align-items:flex-end;font-size:17px;color:#8E89BC}}
.foot b{{font-size:21px;font-weight:500;color:#CFCAF0}}
</style></head><body>
<div class="head"><img class="logo" src="{logo}"><div class="ht"><span class="handle">Romain Trading · RomaiNxTRADES</span><h1>MARKET DIRECTION</h1></div>
<div class="hr"><small>{fdate(asof)}</small><b>Où trader cette semaine ?</b></div></div>
<div class="glow"></div>
<div class="cols">{panel('EUROPE', eu)}{panel('ÉTATS-UNIS', us)}</div>
<div class="foot"><b>@romaintrading</b><span>Graphiques daily · MME 8, MME 21, SMA 50, SMA 200 · Europe via ETF · ceci n'est pas un conseil en investissement</span></div>
</body></html>"""

with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={'width': 1600, 'height': 900}, device_scale_factor=1)
    pg.set_content(page); pg.wait_for_timeout(500)
    over = pg.evaluate('document.body.scrollHeight')
    pg.screenshot(path=out_path)
    b.close()
print(json.dumps({'asof': asof, 'height': over, 'indices': {a['name']: [a['date'], a['score'], a['ftd']] for a in us + eu}}, ensure_ascii=False))
