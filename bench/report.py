#!/usr/bin/env python3
"""bench/results/*/summary.json 을 마크다운 표로 합친다. 사용: bench/report.py"""
import glob, json, os
HERE = os.path.dirname(os.path.abspath(__file__))
rows = []
for f in sorted(glob.glob(f'{HERE}/results/*/summary.json')):
    s = json.load(open(f)); runs = s['runs']; n = len(runs); ts = list(runs[0].keys())
    passed = sum(r[t]['ok'] for r in runs for t in ts); total = n * len(ts)
    wall = sum(r[t]['wall'] for r in runs for t in ts) / n
    toks = [r[t]['tok_s'] for r in runs for t in ts if r[t]['tok_s']]
    mem = s['ps'].split()[2] + s['ps'].split()[3] if len(s['ps'].split()) > 3 else '?'
    per = ' '.join(f"{t}:{sum(r[t]['ok'] for r in runs)}/{n}" for t in ts)
    rows.append((s['model'], mem, f"{sum(toks)/len(toks):.0f}", f"{passed}/{total}", f"{wall:.0f}s", per, 'on' if s['think'] else 'off'))
print('| 모델 | 로드 | tok/s | 정답 | 합산시간(평균/회) | 과제별 | thinking |')
print('|---|---|---|---|---|---|---|')
for r in rows: print('| ' + ' | '.join(r) + ' |')
