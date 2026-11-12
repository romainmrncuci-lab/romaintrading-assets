// node recap_data.js <page html or json> <snapshot.json>  -> prints JSON with everything the visual needs
const fs = require('fs');
const [pagePath, snapPath] = process.argv.slice(2);
let html = fs.readFileSync(pagePath, 'utf8');
try { const j = JSON.parse(html); html = (j.data || j).text || html; } catch (e) {}
const calcScript = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].map((m) => m[1]).find((s) => s.includes("dash.calc('regime'"));
const calcs = {};
global.window = {};
global.dash = {calc: (id, o) => { calcs[id] = o; }, loader: () => {}, params: () => ({}), setParams: () => {}};
eval(calcScript);
let snap = JSON.parse(fs.readFileSync(snapPath, 'utf8')); snap = snap.rows || snap;
const v = {snapshot: snap};
for (const id of ['asof', 'sector_perf', 'signals', 'regime', 'matrix', 'assets', 'rrg']) v[id] = calcs[id].fn(...calcs[id].inputs.map((i) => v[i]));
if ((Date.now() - Date.parse(v.asof + 'T00:00:00Z')) / 864e5 > 5) throw new Error('snapshot is stale: last session ' + v.asof);
const H = 20;
const mat = v.matrix.filter((r) => r.horizon === H);
const now = v.rrg.filter((r) => r.step === 0);
const leaders = now.filter((r) => r.ratio > 100 && r.mom >= 100).sort((a, b) => b.ratio - a.ratio).slice(0, 4);
const taken = new Set(leaders.map((r) => r.symbol));
const out = {
  asof: v.asof,
  regime: Object.fromEntries(v.regime.map((r) => [r.horizon, r])),
  assets: v.assets.filter((r) => r.horizon === H).sort((a, b) => b.tilt - a.tilt),
  up: mat.filter((r) => r.expected > 0).sort((a, b) => b.expected - a.expected).slice(0, 4),
  down: mat.filter((r) => r.expected < 0).sort((a, b) => a.expected - b.expected).slice(0, 4),
  leaders,
  gaining: now.filter((r) => r.mom > 100 && !taken.has(r.symbol)).sort((a, b) => b.mom - a.mom).slice(0, 4),
  losing: now.filter((r) => r.mom < 100).sort((a, b) => a.mom - b.mom).slice(0, 4),
  perf: v.sector_perf.filter((r) => r.symbol !== 'SPY').map((r) => ({symbol: r.symbol, name: r.name, rel: r.r20})).sort((a, b) => b.rel - a.rel),
};
const ser = (k) => snap.filter((r) => r.series === k).map((r) => ({date: String(r.date).slice(0, 10), v: Number(r.value)})).sort((x, y) => (x.date < y.date ? -1 : 1)).slice(-22);
out.lines = ['XLK', 'XLC', 'XLY', 'XLF', 'XLI', 'XLB', 'XLE', 'XLV', 'XLP', 'XLU', 'XLRE', 'SPY'].map((k) => { const s = ser(k); return {symbol: k, pts: s.map((p) => ({date: p.date, v: (100 * p.v) / s[0].v}))}; });
process.stdout.write(JSON.stringify(out));
