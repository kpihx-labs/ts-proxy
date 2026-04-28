# --- Dynamic Configuration (Extracted from pyproject.toml) ---
PKG_NAME     := $(shell grep -m 1 name pyproject.toml | tr -s ' ' | tr -d '"' | tr -d "'" | cut -d' ' -f3)
PKG_DIR_NAME := $(subst -,_,$(PKG_NAME))
PKG_DIR      := src/$(PKG_DIR_NAME)
VERSION      := $(shell grep -m 1 version pyproject.toml | tr -s ' ' | tr -d '"' | tr -d "'" | cut -d' ' -f3)
DOCKER_IMAGE := kpihx/$(PKG_NAME):latest

# --- System Paths ---
REAL_USER := $(if $(SUDO_USER),$(SUDO_USER),$(USER))
REAL_HOME := $(shell getent passwd $(REAL_USER) | cut -d: -f6)
BIN_DIR   := $(REAL_HOME)/.local/bin
DATA_DIR  := $(REAL_HOME)/.$(PKG_NAME)

# --- Tooling ---
UV     := $(shell command -v uv 2>/dev/null || echo uv)
PYTHON := $(UV) run python
PYTEST := $(PYTHON) -m pytest

.PHONY: help uv-audit uv-format uv-install uv-link uv-unlink uv-uninstall uv-test docker-build docker-link docker-install docker-uninstall docker-logs git-commit git-tag git-release

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

uv-check: uv-format uv-fix uv-compile uv-audit uv-test ## Full quality gate: format → fix → compile → audit → test

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

# --- Docker (Sovereign Appliance) ---

docker-build: ## Build the Docker image
	@echo "🐳 Building Docker image $(DOCKER_IMAGE)..."
	@docker build -t $(DOCKER_IMAGE) .

docker-link: ## Link the host-side shim to ~/.local/bin
	@mkdir -p $(BIN_DIR)
	@chmod +x scripts/ts_proxy_shim.py
	@ln -sf $(CURDIR)/scripts/ts_proxy_shim.py $(BIN_DIR)/$(PKG_NAME)
	@echo "✅ Docker shim installed in $(BIN_DIR)/$(PKG_NAME)"

docker-install: docker-build docker-link ## Full Docker-based installation

docker-uninstall: ## Remove Docker artifacts and shim
	@rm -f $(BIN_DIR)/$(PKG_NAME)
	@docker rmi $(DOCKER_IMAGE) 2>/dev/null || true
	@echo "✅ $(PKG_NAME) uninstalled from Docker."

docker-logs: ## View persistent logs from the host data directory
	@if [ -f $(DATA_DIR)/proxy.log ]; then \
		tail -f $(DATA_DIR)/proxy.log; \
	else \
		echo "❌ No logs found at $(DATA_DIR)/proxy.log"; \
	fi

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
	@git push origin $$(git branch --show-current) --tags

# --- Distribution (PyPI & Docker Registry) ---

uv-build: ## Build Python sdist and wheel
	@echo "🏗️ Building Python package v$(VERSION)..."
	@rm -rf dist/
	@$(UV) build

uv-publish: uv-build ## Publish to PyPI (requires UV_PUBLISH_TOKEN)
	@echo "🚀 Publishing v$(VERSION) to PyPI..."
	@$(UV) publish

docker-publish: docker-build ## Push Docker image to registry
	@echo "🚀 Pushing Docker image $(DOCKER_IMAGE)..."
	@docker push $(DOCKER_IMAGE)

git-release: uv-check git-tag git-push uv-publish docker-publish ## Full Release: check → tag → push → publish (Python & Docker)
