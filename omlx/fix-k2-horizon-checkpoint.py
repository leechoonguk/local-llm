#!/usr/bin/env python3
# mlx-community/K2-Horizon-MoVA-36B-A4B-oQ4e 를 oMLX 내장 K2 모듈(0.7.0.dev4+)이 로드할 수 있게 스토어 파일을 고친다.
# 실측(2026-09-24, bench/2026-09-24.s1.k2-horizon.md): 그대로는 두 번 죽는다 —
#   (1) 전문가 키가 리포 동봉 모듈 이름 `mlp.switch_mlp.*` 라 내장 모듈의 `mlp.experts.*` 와 어긋남 → 리네임 + 인덱스 갱신
#   (2) `self_attn.v_router` 가 4~5bit 로 양자화돼 "routers require BF16" → mx.dequantize 로 BF16 복원, config quantization 의 해당 경로 false
# `trust_remote_code` 로 동봉 모듈을 돌리는 우회는 쓰지 않는다(외부 코드 실행). 멱등 — 이미 고친 스토어에 다시 돌려도 no-op.
# 실행은 mlx 가 있는 앱 인터프리터로: ~/.omlx/bin/omlx-cluster-python omlx/fix-k2-horizon-checkpoint.py
# 재다운로드하면 다시 돌린다. 원본 config 는 config.json.orig 로 남긴다.
import json, os, shutil, time
import mlx.core as mx

M = os.path.expanduser('~/.omlx/models/mlx-community/K2-Horizon-MoVA-36B-A4B-oQ4e')
OLD, NEW = '.mlp.switch_mlp.', '.mlp.experts.'
ROUTERS = ('.self_attn.v_router', '.mlp.gate')

cfg_p = os.path.join(M, 'config.json')
if not os.path.exists(cfg_p + '.orig'):
    shutil.copy(cfg_p, cfg_p + '.orig')
cfg = json.load(open(cfg_p)); q = cfg['quantization']
idx_p = os.path.join(M, 'model.safetensors.index.json'); idx = json.load(open(idx_p)); wm = idx['weight_map']

renamed = dequant = 0
for s in sorted(set(wm.values())):
    p = os.path.join(M, s); t0 = time.time()
    w, meta = mx.load(p, return_metadata=True); changed = False
    # (1) switch_mlp -> experts
    for k in [k for k in w if OLD in k]:
        w[k.replace(OLD, NEW)] = w.pop(k); renamed += 1; changed = True
    # (2) 라우터 역양자화
    for k in [k for k in w if k.endswith('.scales') and any(r in k for r in ROUTERS)]:
        base = k[:-len('.scales')]; ov = q.get(base)
        bits = ov['bits'] if isinstance(ov, dict) else q['bits']
        gs = ov['group_size'] if isinstance(ov, dict) else q['group_size']
        mode = ov.get('mode', 'affine') if isinstance(ov, dict) else q.get('mode', 'affine')
        w[base + '.weight'] = mx.dequantize(w[base + '.weight'], w[k], w.get(base + '.biases'),
                                            group_size=gs, bits=bits, mode=mode).astype(mx.bfloat16)
        del w[k]; w.pop(base + '.biases', None); wm.pop(k, None); wm.pop(base + '.biases', None)
        q[base] = False; dequant += 1; changed = True
    if changed:
        tmp = p[:-len('.safetensors')] + '.tmp.safetensors'   # save_safetensors 가 확장자를 강제한다
        mx.save_safetensors(tmp, w, metadata=meta); mx.eval(); os.replace(tmp, p)
        print(f'{s}: rewritten in {time.time()-t0:.1f}s')
    else:
        print(f'{s}: no change')
    del w; mx.clear_cache()

idx['weight_map'] = {(k.replace(OLD, NEW) if OLD in k else k): v for k, v in wm.items()}
json.dump(idx, open(idx_p, 'w'), indent=2); json.dump(cfg, open(cfg_p, 'w'), indent=2)
print(f'renamed {renamed} keys, dequantized {dequant} router tensors')
