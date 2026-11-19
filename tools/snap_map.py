#!/usr/bin/env python3
"""Build map.json for build_snapshot.py from this session's own tool results (no hand mapping).

Usage: python3 snap_map.py map.json
Scans the newest session transcript (~/.claude/projects/*/*.jsonl) for the latest saved results of:
  Twelve Data get_time_series (key = symbol), FMP commodity GCUSD (GOLD), FMP indexes ^VIX (VIX),
  Alpha Vantage TREASURY_YIELD (US10Y). Prints the keys found.
"""
import glob, json, os, re, sys

transcript = max(glob.glob(os.path.expanduser('~/.claude/projects/*/*.jsonl')), key=os.path.getmtime)
uses, found = {}, {}
for line in open(transcript):
    try:
        d = json.loads(line)
    except Exception:
        continue
    content = d.get('message', {}).get('content')
    if not isinstance(content, list):
        continue
    for b in content:
        if b.get('type') == 'tool_use':
            name, inp = b['name'], b.get('input') or {}
            key = None
            if name.endswith('get_time_series'):
                key = (inp.get('symbol') or '').upper() or None
            elif name.endswith('commodity') and inp.get('symbol') == 'GCUSD':
                key = 'GOLD'
            elif name.endswith('indexes') and inp.get('symbol') == '^VIX':
                key = 'VIX'
            elif name.endswith('TREASURY_YIELD'):
                key = 'US10Y'
            if key:
                uses[b['id']] = key
        elif b.get('type') == 'tool_result' and b.get('tool_use_id') in uses:
            c = b.get('content')
            text = c if isinstance(c, str) else ''.join(x.get('text', '') for x in c or [] if isinstance(x, dict))
            m = re.search(r'saved to (/\S+?\.txt)', text)
            if m and os.path.exists(m.group(1)):
                found[uses[b['tool_use_id']]] = m.group(1)
json.dump(found, open(sys.argv[1], 'w'), indent=1)
print(f"{len(found)} séries : " + ', '.join(sorted(found)))
