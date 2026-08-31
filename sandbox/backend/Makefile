.PHONY: help install dev down migrate migrate-gen migrate-down verify verify-fast test test-fast fix lint typecheck clean

UV := uv

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-12s\033[0m %s\n", $$1, $$2}'

install: ## Install dependencies (uv sync)
	$(UV) sync

# The host port comes from the root .env (BACKEND_PORT); start.sh reads it.
BACKEND_PORT ?= $(shell sed -n 's/^BACKEND_PORT[[:space:]]*=[[:space:]]*\([0-9]*\).*/\1/p' ../.env 2>/dev/null || true)
BACKEND_PORT := $(if $(BACKEND_PORT),$(BACKEND_PORT),8000)

dev: ## Run backend locally (migrate + uvicorn on BACKEND_PORT, reload)
	ENV=local BACKEND_PORT=$(BACKEND_PORT) ./scripts/start.sh

down: ## Stop backend (kill uvicorn on BACKEND_PORT)
	lsof -ti:$(BACKEND_PORT) | xargs kill -9 2>/dev/null; echo "==> stopped :$(BACKEND_PORT)"

migrate: ## Apply alembic migrations to head
	.venv/bin/alembic upgrade head

migrate-down: ## Roll back the most recent migration (alembic downgrade -1)
	.venv/bin/alembic downgrade -1

migrate-gen: ## Generate a new migration from model changes (usage: make migrate-gen m="msg")
	@test -n "$(strip $(m))" || { echo 'ERROR: non-empty m="<message>" is required - the message becomes the filename slug'; exit 1; }
	@next=$$(($(shell ls alembic/versions/[0-9]*_*.py 2>/dev/null | xargs -L1 basename 2>/dev/null | cut -d_ -f1 | sort -n | tail -1) + 1)); \
		echo "==> new migration rev: $$next"; \
		.venv/bin/alembic revision --autogenerate --rev-id $$next -m "$(m)"

verify: lint typecheck test ## Run lint, typecheck, and test (fail-fast)

test: ## Run tests (pytest)
	.venv/bin/pytest -q

test-fast: ## Run tests without the coverage gate (usage: make test-fast t="tests/api/test_x.py")
	.venv/bin/pytest -q --no-cov $(t)

verify-fast: lint typecheck test-fast ## Fast iteration gate — lint+typecheck+tests without the coverage gate
	@true

fix: ## Auto-fix lint and formatting (ruff --fix + format; alembic 제외 — 마이그레이션은 불변 산출물)
	.venv/bin/ruff check --fix app tests
	.venv/bin/ruff format app tests

lint: ## Lint (ruff)
	.venv/bin/ruff check app alembic tests

typecheck: ## Type-check (pyright)
	.venv/bin/pyright

clean: ## Remove test, lint, coverage, and Python caches
	rm -rf .coverage .coverage.* .pytest_cache .ruff_cache cov_html htmlcov
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
