# --- Dynamic Configuration (Extracted from pyproject.toml) ---
PKG_NAME     := $(shell grep -m 1 name pyproject.toml | tr -s ' ' | tr -d '"' | tr -d "'" | cut -d' ' -f3)
PKG_DIR_NAME := $(subst -,_,$(PKG_NAME))
PKG_DIR      := src/$(PKG_DIR_NAME)
VERSION      := $(shell grep -m 1 version pyproject.toml | tr -s ' ' | tr -d '"' | tr -d "'" | cut -d' ' -f3)

# --- Tooling ---
UV     := $(shell command -v uv 2>/dev/null || echo uv)
PYTHON := $(UV) run python
PYTEST := $(PYTHON) -m pytest

.PHONY: help uv-audit uv-format uv-install uv-link uv-unlink uv-uninstall uv-test git-commit git-tag git-release

help: ## Show help
	@grep -E '^[a-zA-Z_-]+:.*?##' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# --- UV (Local Dev) ---

uv-audit: ## Run linting and style checks (Ruff)
	@echo "🔍 Running static analysis on $(PKG_DIR)..."
	@$(UV) run ruff check $(PKG_DIR) tests/

uv-format: ## Auto-format code (Ruff)
	@echo "🎨 Formatting code..."
	@$(UV) run ruff format $(PKG_DIR) tests/

uv-fix: ## Auto-fix linting issues (Ruff)
	@echo "🛠️ Auto-fixing issues..."
	@$(UV) run ruff check --fix $(PKG_DIR) tests/

uv-compile: ## Verify Python syntax compilation
	@echo "⚙️ Compiling source files..."
	@$(PYTHON) -m py_compile $(shell find $(PKG_DIR) -name "*.py")

uv-test: ## Run all tests
	@echo "🧪 Running test suite..."
	@$(PYTEST) -v tests/

uv-check: uv-format uv-fix uv-compile uv-audit uv-test ## Development quality gate: format → fix → compile → audit → test

audit: ## Audit infrastructure security (permissions, umask)
	@echo "🛡️ Auditing infrastructure..."
	@$(PYTHON) scripts/audit_infra.py

check: uv-check audit ## Full Sovereign Gate: Dev checks + Infra Audit

uv-install: ## Install locally using uv tool
	@echo "📦 Installing $(PKG_NAME) v$(VERSION) locally..."
	@$(UV) tool install . --force

uv-link: ## Install in editable mode (for development)
	@echo "🔗 Linking $(PKG_NAME) for dev..."
	@$(UV) tool install --editable . --force

uv-unlink: ## Uninstall local editable/tool version
	@echo "⌫ Unlinking $(PKG_NAME)..."
	@$(UV) tool uninstall $(PKG_NAME)

uv-uninstall: uv-unlink ## Alias for uv-unlink

# --- Git (Release & Lifecycle) ---

git-init-hooks: ## Install git pre-commit hook
	@echo "🪝 Installing git pre-commit hook..."
	@echo "#!/bin/sh\nmake uv-check" > .git/hooks/pre-commit
	@chmod +x .git/hooks/pre-commit
	@echo "✅ Pre-commit hook installed."

git-status: ## Show git status 
	@git status

git-commit: uv-check ## Format, Audit and Commit changes (requires msg="...")
	@if [ -z "$(msg)" ]; then echo "❌ Error: Use 'make git-commit msg=\"Your message\"'"; exit 1; fi
	@git add .
	@git commit -m "$(msg)"

git-tag: ## Create a new git tag from pyproject.toml version
	@echo "🏷️ Tagging version v$(VERSION)..."
	@git tag -a v$(VERSION) -m "Release v$(VERSION)"

git-push: ## Push current branch and tags to all remotes
	@git push github $$(git branch --show-current) --tags
	@git push gitlab $$(git branch --show-current) --tags

push: git-push ## Alias for git-push

# --- Distribution (PyPI) ---

uv-build: ## Build Python sdist and wheel
	@echo "🏗️ Building Python package v$(VERSION)..."
	@rm -rf dist/
	@$(UV) build

uv-publish: uv-build ## Publish to PyPI (requires UV_PUBLISH_TOKEN)
	@echo "🚀 Publishing v$(VERSION) to PyPI..."
	@$(UV) publish

git-release: uv-check git-tag git-push uv-publish ## Full Release: check → tag → push → publish (Python)
