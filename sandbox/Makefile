.PHONY: probe-external-api check-omp-types continuity-selftest continuity-report hook-report check-api-flow-verbose help build up down infra-up infra-down db-init db-query logs ps clean docker-clean verify check-backend-domain check-backend-migrations check-backend-table-design check-backend-auth check-backend-exceptions check-backend-api-http check-backend-router-params check-backend-naming check-backend-transaction check-backend-batch check-backend-tests check-backend-middleware check-backend-app-setup check-backend-core-config check-backend-rate-limit check-backend-background-tasks check-backend-ownership check-backend-audit-log check-backend-redis-cache check-backend-file-upload check-backend-sse check-backend-api-keys check-backend-integration check-backend-integration-configuration check-environment check-code-layout check-tooling check-frontend-code check-ast-rules check-omp-types check-omp-hooks check-omp-rules check-omp-skills check-makefiles check-decks-sync check-verify continuity-selftest continuity-report endure-arm endure hook-report check-api-flow check-api-flow-verbose probe-external-api %

DC := docker compose

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

build: ## Build all service images
	$(DC) build

up: ## Start the full stack (detached)
	$(DC) up -d --build

down: ## Stop and remove all containers
	$(DC) down

infra-up: ## Start only infrastructure (postgres + redis + phoenix)
	$(DC) up -d postgres redis phoenix

infra-down: ## Stop infrastructure only (postgres + redis + phoenix)
	$(DC) down postgres redis phoenix

db-init: ## Reset DB: drop volumes, recreate, run migrations
	$(DC) down -v postgres
	$(DC) up -d --wait postgres
	$(MAKE) -C backend migrate

db-query: ## Run SQL against the app database at head (usage: make db-query q="SELECT ...")
	@$(MAKE) -C backend migrate >/dev/null
	@test -n '$(q)' || { echo 'usage: make db-query q="SELECT ..."' >&2; exit 2; }
	@Q="$(q)"; $(DC) exec -T postgres psql -U $${POSTGRES_USER:-app} -d $${POSTGRES_DB:-app} -P pager=off -c "$$Q"

logs: ## Tail logs from all services
	$(DC) logs -f

ps: ## List running services
	$(DC) ps

clean: ## Remove backend and frontend caches
	$(MAKE) -C backend clean
	$(MAKE) -C frontend clean

docker-clean: ## Stop services and remove Docker volumes (data loss!)
	$(DC) down -v

check-backend-domain: ## Check backend domain CRUD structure
	node .omp/hooks/post/check-backend-domain.ts

check-backend-migrations: ## Check ORM ↔ DB sync (alembic check)
	node .omp/hooks/post/check-backend-migrations.ts

check-backend-table-design: ## Check backend table design invariants (1NF, keys, constraints)
	node .omp/hooks/post/check-backend-table-design.ts

check-backend-auth: ## Check backend auth conventions
	node .omp/hooks/post/check-backend-auth.ts

check-backend-exceptions: ## Check core exception policy (raise only core exceptions)
	node .omp/hooks/post/check-backend-exceptions.ts

check-backend-api-http: ## Check router ↔ .http sync
	node .omp/hooks/post/check-backend-api-http.ts

check-backend-router-params: ## Check backend router parameter standard (path/body/dep/query)
	node .omp/hooks/post/check-backend-router-params.ts

check-backend-naming: ## Check backend naming conventions
	node .omp/hooks/post/check-backend-naming.ts

check-backend-transaction: ## Check backend transaction conventions
	node .omp/hooks/post/check-backend-transaction.ts

check-backend-batch: ## Check backend batch job conventions
	node .omp/hooks/post/check-backend-batch.ts

check-backend-tests: ## Check backend test standard (per-domain, 8 cases, auth, conftest)
	node .omp/hooks/post/check-backend-tests.ts

check-backend-middleware: ## Check backend middleware (CORS, security headers, request ID, logging)
	node .omp/hooks/post/check-backend-middleware.ts

check-backend-app-setup: ## Check backend app setup (health, OpenAPI metadata, /api/v1)
	node .omp/hooks/post/check-backend-app-setup.ts

check-backend-core-config: ## Check backend core config (settings validators, DB pool, error schema)
	node .omp/hooks/post/check-backend-core-config.ts

check-backend-rate-limit: ## Check backend rate limiting (slowapi on login/signup)
	node .omp/hooks/post/check-backend-rate-limit.ts

check-backend-background-tasks: ## Check backend background tasks (BackgroundTasks pattern)
	node .omp/hooks/post/check-backend-background-tasks.ts

check-backend-ownership: ## Check backend ownership checks (created_by verification)
	node .omp/hooks/post/check-backend-ownership.ts

check-backend-audit-log: ## Check backend audit log endpoint
	node .omp/hooks/post/check-backend-audit-log.ts

check-backend-redis-cache: ## Check backend Redis cache (TTL + invalidation)
	node .omp/hooks/post/check-backend-redis-cache.ts

check-backend-file-upload: ## Check backend file upload (size + content-type guards)
	node .omp/hooks/post/check-backend-file-upload.ts

check-backend-sse: ## Check backend SSE (EventSourceResponse)
	node .omp/hooks/post/check-backend-sse.ts

check-backend-api-keys: ## Check backend API keys (X-API-Key dependency)
	node .omp/hooks/post/check-backend-api-keys.ts

check-backend-integration: ## Check backend external API integration contract
	node .omp/hooks/post/check-backend-integration.ts


check-backend-integration-configuration: ## Check database-managed integration configuration contract
	node .omp/hooks/post/check-backend-integration-configuration.ts


check-environment: ## Check .env + settings.py + root↔backend sync
	node .omp/hooks/post/check-environment.ts

check-code-layout: ## Check code layout (comments, banners, constants, member order)
	node .omp/hooks/post/check-code-layout.ts

check-tooling: ## Check tooling language policy (TypeScript hooks, no Python scripts)
	node .omp/hooks/post/check-tooling.ts

check-frontend-code: ## Check frontend code conventions
	node .omp/hooks/post/check-frontend-code.ts

check-ast-rules: ## Prove every ast-grep rule fires (valid/invalid cases)
	node .omp/hooks/post/check-ast-rules.ts

check-omp-types: ## Type-check the harness TypeScript (.omp/**/*.ts)
	node .omp/hooks/post/check-omp-types.ts

check-omp-hooks: ## Check OMP hooks directory structure
	node .omp/hooks/post/check-omp-hooks.ts

check-omp-rules: ## Verify .omp/rules/ files are in sync with AGENTS.md
	node .omp/hooks/post/check-omp-rules.ts
check-omp-skills: ## Check skills catalog against discovered SKILL.md files
	node .omp/hooks/post/check-omp-skills.ts


check-makefiles: ## Check Makefile targets consistency
	node .omp/hooks/post/check-makefiles.ts

check-decks-sync: ## Check decks/harness-rules/slides.md mentions all rules/hooks/AST dirs
	node .omp/hooks/post/check-decks-sync.ts

check-verify: ## Run backend + frontend verify (lint, typecheck, test/build)
	node .omp/hooks/post/check-verify.ts

continuity-selftest: ## Drive the continuity extension against a fake host
	node .omp/extensions/continuity/selftest.ts

continuity-report: ## Report whether continuity interventions broke their loops
	node .omp/extensions/continuity/report.ts

hook-report: ## Report what the post hooks actually cost and which never warned
	node .omp/hooks/lib/hook-metrics.ts

check-api-flow: ## Run every api/*.http against the running stack (proves state neutrality)
	node .omp/hooks/lib/backend-api-flow.ts

check-api-flow-verbose: ## Same, printing every block's declared vs actual status
	node .omp/hooks/lib/backend-api-flow.ts --verbose

probe-external-api: ## Measure a provider before integrating it (usage: make probe-external-api url='https://host/api/KEY/SVC/json/{start}/{end}' filter='K=V' since='K=YYYYMMDD')
	@test -n '$(url)' || { echo "usage: make probe-external-api url='https://host/api/KEY/SVC/json/{start}/{end}' [filter='K=V'] [since='K=YYYYMMDD'] [root=/WRAPPER]" >&2; exit 2; }
	@node .omp/hooks/lib/backend-external-api-probe.ts --url '$(url)' \
		$(if $(filter),--filter '$(filter)') $(if $(since),--since '$(since)') $(if $(root),--root '$(root)')

verify: check-backend-domain check-backend-migrations check-backend-table-design check-backend-auth check-backend-exceptions check-backend-api-http check-backend-router-params check-backend-naming check-backend-transaction check-backend-batch check-backend-tests check-backend-middleware check-backend-app-setup check-backend-core-config check-backend-rate-limit check-backend-background-tasks check-backend-ownership check-backend-audit-log check-backend-redis-cache check-backend-file-upload check-backend-sse check-backend-api-keys check-backend-integration check-backend-integration-configuration check-environment check-code-layout check-tooling check-frontend-code check-ast-rules check-omp-types check-omp-hooks check-omp-rules check-omp-skills check-makefiles check-decks-sync check-verify ## Run all OMP hooks + backend + frontend verify
