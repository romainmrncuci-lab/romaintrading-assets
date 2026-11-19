#!/usr/bin/env python3
"""Build the community dashboard snapshot.

Usage: python3 build_snapshot.py map.json out.json
map.json: {"XLK": "/path/to/saved/tool/result.txt", ..., "GOLD": ..., "VIX": ..., "US10Y": ...}
Each path is a tool result saved to a file (Twelve Data CSV, FMP JSON list, Alpha Vantage CSV or preview JSON).
Writes {"rows": [{"series", "date", "value"}...]} keeping the last 270 sessions of each series, oldest first.
"""
import csv, datetime, io, json, sys

KEEP = 270
EXPECTED = ["XLK", "XLC", "XLY", "XLF", "XLI", "XLB", "XLE", "XLV", "XLP", "XLU", "XLRE", "SPY", "UUP", "USO", "GOLD", "VIX", "US10Y"]
# Séries complémentaires (tendance des indices, industries) : utilisées si présentes, sinon ignorées avec un avertissement
OPTIONAL = ["QQQ", "IWM", "PBJ", "IHI", "PPH", "IHF", "XBI", "ICLN", "NLR", "SRVR", "KIE", "KBE", "KRE", "IAI", "BLOK",
            "ITB", "PEJ", "XRT", "GDX", "XME", "LIT", "SIL", "REMX", "COPX", "JETS", "IYT", "ITA", "PAVE", "OIH", "TAN",
            "XOP", "IGV", "SKYY", "CIBR", "BOTZ", "QTUM", "SMH", "FDN", "ESPO"]


def parse(text):
    data = None
    try:
        data = json.loads(text)
    except Exception:
        pass
    if isinstance(data, dict):
        if isinstance(data.get("result"), str):
            return parse(data["result"])
        if isinstance(data.get("sample_data"), str):
            return parse(data["sample_data"])
        raise ValueError("unexpected JSON object: " + text[:200])
    if isinstance(data, list):
        out = []
        for r in data:
            v = r.get("price", r.get("close", r.get("value")))
            if r.get("date") and v not in (None, "", "."):
                out.append((str(r["date"])[:10], float(v)))
        return out
    text = text.strip().replace("\r", "")
    if not text:
        raise ValueError("empty result")
    delim = ";" if text.split("\n", 1)[0].count(";") else ","
    reader = csv.DictReader(io.StringIO(text), delimiter=delim)
    out = []
    for r in reader:
        d = r.get("datetime") or r.get("timestamp") or r.get("date")
        v = r.get("close") or r.get("value")
        if d and v not in (None, "", "."):
            try:
                out.append((d[:10], float(v)))
            except ValueError:
                pass
    if not out:
        raise ValueError("no rows parsed: " + text[:200])
    return out


def main():
    mapping = json.load(open(sys.argv[1]))
    missing = [k for k in EXPECTED if k not in mapping]
    if missing:
        sys.exit("missing series: " + ", ".join(missing))
    rows, report = [], []
    today = datetime.date.today()
    now = datetime.datetime.now(datetime.timezone.utc)
    # Séance US en cours (avant 21h15 UTC) : on ignore la barre du jour, incomplète
    cutoff = today if now.hour * 60 + now.minute < 21 * 60 + 15 else today + datetime.timedelta(days=1)
    for key in EXPECTED + OPTIONAL:
        if key not in mapping:
            report.append(f"{key}: ABSENT (ignoré)")
            continue
        try:
            pts = sorted(dict(p for p in parse(open(mapping[key]).read()) if p[0] < cutoff.isoformat()).items())
        except Exception as err:
            if key in OPTIONAL:
                report.append(f"{key}: ERREUR {err} (ignoré)")
                continue
            raise
        pts = pts[-KEEP:]
        last = datetime.date.fromisoformat(pts[-1][0])
        problem = f"only {len(pts)} rows" if len(pts) < 130 else f"latest date {last} is stale" if (today - last).days > 7 else None
        if problem:
            if key in OPTIONAL:
                report.append(f"{key}: {problem} (ignoré)")
                continue
            sys.exit(f"{key}: {problem}")
        report.append(f"{key}: {len(pts)} rows, {pts[0][0]} -> {pts[-1][0]}, last {pts[-1][1]}")
        rows += [{"series": key, "date": d, "value": v} for d, v in pts]
    json.dump({"rows": rows}, open(sys.argv[2], "w"), separators=(",", ":"))
    print("\n".join(report))
    print(f"total rows: {len(rows)}")


if __name__ == "__main__":
    main()
