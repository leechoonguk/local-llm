# local-llm 검증 진입점. 검사는 전부 순수 파일 읽기(서버·네트워크 없음), node 24+ 로 .ts 를 직접 실행한다.
# 타깃 계약(check-harness 가 강제): .claude/rules/<name>.md ↔ .claude/hooks/check-<name>.ts ↔ check-<name> ↔ verify.
.PHONY: check-sandbox-harness-edit check-sandbox-harness-review help verify preflight smoke bake check-harness-proofs check-bench-results check-ollama-modelfile check-omp-models check-omlx-config check-docs-sync check-skills check-harness check-live-sync check-autostart

help: ## 타깃 목록
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-24s\033[0m %s\n", $$1, $$2}'

verify: check-harness check-harness-proofs check-sandbox-harness-review check-sandbox-harness-edit check-bench-results check-ollama-modelfile check-omp-models check-omlx-config check-docs-sync check-skills check-live-sync check-autostart ## 모든 검사 실행 (커밋 전 게이트)

check-bench-results: ## bench/ 결과 기록 표준 (파일명·5절·표·인덱스)
	node .claude/hooks/check-bench-results.ts

check-ollama-modelfile: ## ollama/Modelfile.* ↔ install.sh (Create 주석, num_ctx>num_predict, 샘플링 출처)
	node .claude/hooks/check-ollama-modelfile.ts

check-omp-models: ## omp/models.yml·config.fragment.yml ↔ Modelfile·oMLX (창/출력 일치, 참조 실재)
	node .claude/hooks/check-omp-models.ts

check-omlx-config: ## omlx/*.json ↔ install.sh (reasoning_parser, MTP 중립값, 드래프터 다운로드)
	node .claude/hooks/check-omlx-config.ts

check-docs-sync: ## CLAUDE.md·README ↔ 설정 (기본 코더, 인용 절, 파일 목록)
	node .claude/hooks/check-docs-sync.ts

check-skills: ## .claude/skills/*/SKILL.md 프런트매터·CLAUDE.md 등재
	node .claude/hooks/check-skills.ts

check-harness-proofs: ## sandbox 하네스 합성 프루프 실행 (discipline 신호·additive 가드 경계 — FAIL 0)
	node .claude/hooks/check-harness-proofs.ts

check-sandbox-harness-edit: ## sandbox 하네스 수정 절차(셀 중 수정·피험자 트리 혼입) 검사
	node .claude/hooks/check-sandbox-harness-edit.ts

check-sandbox-harness-review: ## sandbox 규칙이 바깥(bench/·.claude/)을 가리키지 않는지
	node .claude/hooks/check-sandbox-harness-review.ts

check-harness: ## 하네스 자기 검증 (규칙↔검사↔Makefile↔settings.json, 훅 스모크)
	node .claude/hooks/check-harness.ts

check-live-sync: ## 레포 설정 ↔ 라이브 시스템 (~/.omp/agent, ~/.omlx·oMLX.app, Ollama LaunchAgent·모델). 미설치 시스템은 skip
	node .claude/hooks/check-live-sync.ts

check-autostart: ## Ollama·oMLX 자동 시작/재시작이 둘 다 꺼져 있는지 (템플릿·install.sh·brew services·launchd·로그인 항목·oMLX 설정)
	node .claude/hooks/check-autostart.ts

preflight: ## 벤치 셀 발진 전 일괄 점검 — 셀 부재(pgrep)·sandbox 타입체크·decks 동기·sandbox 루트 verify(실제 종료코드). 무효 스텁 4회의 재발 방지(2026-08-28)
	@! pgrep -f "omp -p" >/dev/null || { echo "FAIL: 벤치 셀이 실행 중 — 하네스 편집/발진 금지"; exit 1; }
	$(MAKE) -C sandbox check-omp-types
	$(MAKE) -C sandbox/decks build
	$(MAKE) -C sandbox verify

smoke: ## 베이크 검증 — 서빙·기본 코더 응답·reasoning 분리·MTP 발화·서버가 보는 설정값 (usage: make smoke [MODEL=<id>])
	bash omlx/smoke.sh $(MODEL)

bake: ## 확정 설정을 라이브에 굽는다 — 레포 → ~/.omlx·~/.omp/agent 복사 후 검증된 재시작 + smoke + verify (셀 실행 중이면 거부)
	@! pgrep -f "omp -p" >/dev/null || { echo "FAIL: 벤치 셀이 실행 중 — 베이크 금지"; exit 1; }
	cp omlx/model_settings.json $(HOME)/.omlx/model_settings.json
	cp omlx/model_profiles.json $(HOME)/.omlx/model_profiles.json
	cp omp/models.yml "$$(omp config path | tail -1)/models.yml"
	-$(HOME)/.omlx/bin/omlx restart
	@for i in $$(seq 1 30); do curl -s http://127.0.0.1:9090/v1/models >/dev/null 2>&1 && break; sleep 2; done
	$(MAKE) smoke
	$(MAKE) verify
