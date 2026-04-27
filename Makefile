.PHONY: help install test build audit push run dev clean

help:
	@echo "Available targets:"
	@echo "  install  - Install project dependencies with uv"
	@echo "  test     - Run the test suite"
	@echo "  build    - Build the Docker image"
	@echo "  audit    - Run formatting, linting, and security checks"
	@echo "  push     - Push to git remote"
	@echo "  clean    - Remove build artifacts and caches"

install:
	uv sync

test:
	uv run pytest tests/

build:
	docker build -t ghcr.io/kpihx/ts-proxy:latest .

audit:
	@echo "Running local audit..."
	uv run ruff check src/ tests/
	uv run ruff format --check src/ tests/

push: audit test
	git add .
	git commit -m "chore: automated push via make push" || echo "No changes to commit"
	git push

clean:
	rm -rf .venv/ .pytest_cache/ .ruff_cache/
	find . -type d -name "__pycache__" -exec rm -rf {} +
