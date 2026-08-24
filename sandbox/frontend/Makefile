.PHONY: help install dev down verify lint typecheck build clean

NPM := npm

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "   \033[36m%-12s\033[0m %s\n", $$1, $$2}'

install: ## Install dependencies (npm install)
	$(NPM) install

dev: ## Run Vite dev server (:5173, background)
	nohup npx vite > /tmp/vite.log 2>&1 & disown; echo "==> Frontend PID: $$!"

down: ## Stop frontend (kill Vite on :15173)
	lsof -ti:15173 | xargs kill -9 2>/dev/null; echo "==> stopped"

verify: lint typecheck build ## Run lint, typecheck, and build (fail-fast)

lint: ## Lint (eslint)
	npx eslint .

typecheck: ## Type-check (tsc --noEmit)
	npx tsc --noEmit

build: ## Production build (tsc -b && vite build)
	npx tsc -b && npx vite build

clean: ## Remove build, Vite, and TypeScript caches
	rm -rf dist .vite node_modules/.vite *.tsbuildinfo
