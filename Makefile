# local-llm 검증 진입점. 검사는 전부 순수 파일 읽기(서버·네트워크 없음), node 24+ 로 .ts 를 직접 실행한다.
# 타깃 계약(check-harness 가 강제): .claude/rules/<name>.md ↔ .claude/hooks/check-<name>.ts ↔ check-<name> ↔ verify.
.PHONY: help verify check-bench-results check-ollama-modelfile check-omp-models check-omlx-config check-docs-sync check-skills check-harness check-live-sync check-autostart

help: ## 타깃 목록
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-24s\033[0m %s\n", $$1, $$2}'

verify: check-bench-results check-ollama-modelfile check-omp-models check-omlx-config check-docs-sync check-skills check-harness check-live-sync check-autostart ## 모든 검사 실행 (커밋 전 게이트)

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

check-harness: ## 하네스 자기 검증 (규칙↔검사↔Makefile↔settings.json, 훅 스모크)
	node .claude/hooks/check-harness.ts

check-live-sync: ## 레포 설정 ↔ 라이브 시스템 (~/.omp/agent, ~/.omlx, Ollama LaunchAgent·모델). 미설치 시스템은 skip
	node .claude/hooks/check-live-sync.ts

check-autostart: ## Ollama·oMLX 자동 시작/재시작이 둘 다 꺼져 있는지 (템플릿·install.sh·brew services·launchd·로그인 항목·oMLX 설정)
	node .claude/hooks/check-autostart.ts
