#!/usr/bin/env python3
"""Build map.json for render_md.py from this session's own tool results.

Usage: python3 md_map.py out_map.json [work_dir]
Scans the newest session transcript (~/.claude/projects/*/*.jsonl) for the latest results of:
  FMP indexes ^IXIC / ^GSPC, Alpha Vantage TIME_SERIES_DAILY and TIME_SERIES_WEEKLY for EXSA.DEX / CAC.PAR.
Large results are already saved to files (their path is taken from the result); small ones are written to work_dir.
"""
import glob, json, os, re, sys

out, work = sys.argv[1], (sys.argv[2] if len(sys.argv) > 2 else '.')
transcript = max(glob.glob(os.path.expanduser('~/.claude/projects/*/*.jsonl')), key=os.path.getmtime)
KEYS = {('indexes', '^IXIC'): 'IXIC', ('indexes', '^GSPC'): 'GSPC',
        ('TIME_SERIES_DAILY', 'EXSA.DEX'): 'EXSA_D', ('TIME_SERIES_WEEKLY', 'EXSA.DEX'): 'EXSA_W',
        ('TIME_SERIES_DAILY', 'CAC.PAR'): 'CAC_D', ('TIME_SERIES_WEEKLY', 'CAC.PAR'): 'CAC_W'}
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
            tool = next((t for t in ('indexes', 'TIME_SERIES_DAILY', 'TIME_SERIES_WEEKLY') if b['name'].endswith(t)), None)
            key = KEYS.get((tool, (b.get('input') or {}).get('symbol')))
            if key:
                uses[b['id']] = key
        elif b.get('type') == 'tool_result' and b.get('tool_use_id') in uses:
            c = b.get('content')
            text = c if isinstance(c, str) else ''.join(x.get('text', '') for x in c or [] if isinstance(x, dict))
            key = uses[b['tool_use_id']]
            m = re.search(r'saved to (/\S+?\.txt)', text)
            if m and os.path.exists(m.group(1)):
                found[key] = m.group(1)
            elif text.lstrip().startswith(('timestamp', '[')):
                path = os.path.join(work, f'{key}.txt')
                open(path, 'w').write(text)
                found[key] = path
missing = [k for k in KEYS.values() if k not in found]
if missing:
    sys.exit('missing results: ' + ', '.join(missing))
json.dump(found, open(out, 'w'), indent=1)
print(json.dumps(found, indent=1))
