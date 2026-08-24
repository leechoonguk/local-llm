# Reveal.js — 이 프로젝트의 실제 발표 도구

> **왜 reveal.js인가**: 이 머신의 homebrew node 25가 `llhttp` 라이브러리
> 누락으로 실행 불가 → Slidev의 Vite dev server (`slidev run`)가 동작하지
> 않음. Marp는 세로 잘림(overflow) 문제와 무거운 커뮤니티 테마 문제가 있었음.
> reveal.js는 **빌드/서버 불필요**(CDN 단일 HTML, `file://`로 바로 열림),
> 내장 테마 11종, 마크다운 지원 — 가장 평이 좋음(72k stars, MIT).

## 퀵스타트

```bash
# 전체 덱 빌드 (decks/ 에서) — 마크다운 소스 → 단일 HTML
cd decks && make build

# 브라우저로 열기 (빌드 도구/서버 불필요)
open decks/<name>/slides.html
```

## 파이프라인

```
decks/
├── Makefile                    # build = sync-hashes + build-reveal
├── package.json                # @marp-team/marp-cli (미사용, marpx 테마 제거됨)
├── scripts/
│   ├── sync-hashes.mjs         # 하네스 아티팩트 해시 주석 삽입 (싱크 유지)
│   └── build-reveal.mjs        # slides.md → 단일 reveal.js HTML
└── <deck>/
    ├── slides.md               # 소스 (유일하게 커밋됨)
    └── slides.html             # 산출물 (gitignore)
```

`build-reveal.mjs` 동작:
- `---`로 슬라이드 분할 → `<section data-markdown>` 템플릿에 임베드
- sync 해시 주석/headmatter 제거
- CDN: reveal.js 5.2.1 + markdown/notes 플러그인 + mermaid 11
- mermaid는 **현재 보이는 슬라이드만** 렌더링 (숨겨진 슬라이드는 NaN 실패)

## 테마

`--theme` 인자로 전환 가능 (기본 `dracula`):

| 테마 | 스타일 |
|---|---|
| `dracula` (기본) | 어두운 보라 (#282a36) |
| `black` / `white` | 무채색 |
| `league` | 어두운 블루 (기본 느낌) |
| `moon` | 어두운 인디고 |
| `solarized` | 밝은 베이지 |
| `sky` / `beige` | 밝은 파스텔 |

## 핵심 문법 (Marp와 거의 동일)

```markdown
---
marp: true      # 이 줄은 reveal.js 빌드에서 무시됨 (headmatter 제거)
---

# 첫 슬라이드

---

# 둘째 슬라이드
```

- `---` 로 슬라이드 분리 (Marp와 동일)
- HTML 주석 `<!-- ... -->` 는 렌더링 안 됨 (싱크 해시 주석 활용)
- Mermaid 코드 펜스는 그대로 동작 (CDN + on-demand 렌더링)

## 세로 넘침 (overflow) 해결

Marp는 `overflow: hidden`이라 콘텐츠가 잘렸지만, reveal.js는 넘치는
콘텐츠를 **스크롤로 노출** — 잘림 없음. 테이블이 많은 슬라이드도 안전.

## 하네스 싱크 (decks-sync)

`make build`가 `<!-- sync: <name>=<sha256> -->` 주석을 slides.md에 삽입.
`check-decks-sync.ts`(make verify)가 이 해시를 실파일과 비교:

- 룰/훅/AST 규칙 **내용 수정** 후 `make build` 안 하면 → `hash mismatch` 경고
- 룰/훅 **추가/삭제** 후 덱 미반영 → `not mentioned` 경고

하네스 수정 시: `.omp/` 변경 → 덱 내용 갱신 → `make build` → `make verify`

## Slidev (선택)

Slidev는 여전히 유효한 도구 (Vue 컴포넌트, Monaco, 발표자 모드). node 25가
고쳐지거나 nvm node로 hub PATH가 잡히면:

```bash
pnpm create slidev
pnpm run dev      # :3030
pnpm run build
pnpm run export   # PDF (playwright-chromium 필요)
```

자세한 문법은 이 스킬의 다른 references (`core-syntax`, `core-frontmatter`,
`core-layouts`, `code-line-highlighting`, `diagram-mermaid`) 참조.
