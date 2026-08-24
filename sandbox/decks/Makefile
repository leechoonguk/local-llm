.PHONY: help install build clean

MARP := npx marp
INJECT := node scripts/inject-mermaid.mjs
SYNC := node scripts/sync-hashes.mjs
REVEAL := node scripts/build-reveal.mjs
THEME := dracula

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "   \033[36m%-12s\033[0m %s\n", $$1, $$2}'

install: ## Install dependencies (npm install)
	npm install

build: ## Refresh sync hashes, build all decks to single-file reveal.js HTML
	@for deck in */slides.md; do \
		dir=$$(dirname $$deck); \
		$(SYNC) $$dir && \
		$(REVEAL) $$dir --theme $(THEME); \
	done

clean: ## Remove generated HTML files
	rm -f */slides.html
