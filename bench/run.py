#!/usr/bin/env python3
"""Ollama 코딩 모델 검증 하네스.

사용: bench/run.py MODEL[:tag] [--repeat N] [--no-think]
  - 모델을 **단일 로드**한다(실행 전 `ollama ps`의 다른 모델을 전부 내린다).
  - tasks/<t>_prompt.md 를 /api/chat 으로 보내고, 코드 블록을 뽑아 tasks/<t>_test.* 로 실행 채점한다.
  - 결과: bench/results/<model>/<t>/{raw.json,sol.*,test} + summary.json. 표는 bench/report.py 로.
"""
import argparse, json, os, re, shutil, subprocess, sys, time, urllib.request
HERE = os.path.dirname(os.path.abspath(__file__))
TASKS = [  # (id, lang, 저장 파일명, 테스트 명령)
    ('t1', 'python', 'lru_ttl.py', ['python3', 't1_test.py']),
    ('t2', 'python', 'sol.py', ['python3', 't2_test.py']),
    ('t3', 'python', 'sol.py', ['bash', 't3_test.sh']),
    ('t4', 'javascript', 'sol.js', ['node', 't4_test.js']),
]

def chat(model, prompt, think):
    body = {'model': model, 'messages': [{'role': 'user', 'content': prompt}], 'stream': False, 'think': think}
    req = urllib.request.Request('http://127.0.0.1:11434/api/chat', data=json.dumps(body).encode(),
                                 headers={'Content-Type': 'application/json'})
    t = time.time(); r = json.loads(urllib.request.urlopen(req, timeout=1800).read()); r['wall'] = time.time() - t
    return r

def extract(text, lang):
    m = re.findall(r"```(?:%s)?\n(.*?)```" % lang, text, re.S)
    return m[-1] if m else text

def unload_others(model):
    out = subprocess.run(['ollama', 'ps'], capture_output=True, text=True).stdout.splitlines()[1:]
    for line in out:
        name = line.split()[0]
        if name != model and name != model + ':latest':
            subprocess.run(['ollama', 'stop', name], capture_output=True)

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('model'); ap.add_argument('--repeat', type=int, default=1)
    ap.add_argument('--no-think', action='store_true'); a = ap.parse_args()
    think = not a.no_think
    out = os.path.join(HERE, 'results', a.model.replace(':', '_').replace('/', '_')); os.makedirs(out, exist_ok=True)
    unload_others(a.model)
    chat(a.model, 'Reply with exactly: OK', False)  # 로드 + 워밍업
    ps = subprocess.run(['ollama', 'ps'], capture_output=True, text=True).stdout.strip().splitlines()[-1]
    res = {'model': a.model, 'think': think, 'ps': ps, 'runs': []}
    for i in range(a.repeat):
        run = {}
        for t, lang, fname, cmd in TASKS:
            r = chat(a.model, open(f'{HERE}/tasks/{t}_prompt.md').read(), think); msg = r['message']
            d = os.path.join(out, f'{t}' if a.repeat == 1 else f'{t}_r{i}'); shutil.rmtree(d, ignore_errors=True); os.makedirs(d)
            for f in os.listdir(f'{HERE}/tasks'):
                if f.startswith(t + '_test'): shutil.copy(f'{HERE}/tasks/{f}', d)
            open(os.path.join(d, fname), 'w').write(extract(msg['content'], lang))
            open(os.path.join(d, 'raw.json'), 'w').write(json.dumps(r, indent=1, ensure_ascii=False))
            try:
                p = subprocess.run(cmd, cwd=d, capture_output=True, text=True, timeout=60); ok = p.returncode == 0; err = (p.stderr or p.stdout)[-300:]
            except subprocess.TimeoutExpired:
                ok, err = False, 'test timeout'
            run[t] = {'ok': ok, 'wall': round(r['wall'], 1), 'eval_tok': r.get('eval_count'),
                      'tok_s': round(r['eval_count'] / (r['eval_duration'] / 1e9), 1) if r.get('eval_duration') else None,
                      'prompt_tok': r.get('prompt_eval_count'), 'think_chars': len(msg.get('thinking') or ''), 'err': '' if ok else err}
            print(f"{a.model} r{i} {t} {'OK  ' if ok else 'FAIL'} {run[t]['wall']:>6}s {run[t]['tok_s']} tok/s think={run[t]['think_chars']}", flush=True)
        res['runs'].append(run)
    json.dump(res, open(os.path.join(out, 'summary.json'), 'w'), indent=1)
    print(ps)

if __name__ == '__main__': main()
