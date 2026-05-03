PYTHON ?= python3
CONFIG ?=
RUN = $(PYTHON) -m repo_wiki.main

# Development targets
.PHONY: help install-dev lint format typecheck test coverage clean

help:
	@echo "repo-wiki development targets:"
	@echo "  install-dev   Install in development mode with dev dependencies"
	@echo "  lint          Run ruff linter"
	@echo "  format        Format code with ruff"
	@echo "  typecheck     Run mypy type checking"
	@echo "  test          Run tests"
	@echo "  coverage      Run tests with coverage report"
	@echo "  clean          Remove build artifacts"
	@echo ""
	@echo "repo-wiki CLI targets:"
	@echo "  ai-init       Initialize repository"
	@echo "  ai-index      Build search index"
	@echo "  ai-update     Incremental update"
	@echo "  ai-sync       Sync wiki"
	@echo "  ai-verify     Verify wiki quality"
	@echo "  ai-cost       Estimate LLM costs"

install-dev:
	pip install -e ".[dev]"

lint:
	ruff check .

format:
	ruff format .

typecheck:
	mypy repo_wiki

test:
	pytest

coverage:
	pytest --cov=repo_wiki --cov-report=term-missing --cov-report=html

clean:
	rm -rf build/ dist/ *.egg-info/ .pytest_cache/ .coverage htmlcov/
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

# repo-wiki CLI targets
ai-init:
	$(RUN) init $(if $(CONFIG),--config $(CONFIG),)

ai-index:
	$(RUN) index $(if $(CONFIG),--config $(CONFIG),)

ai-update:
	$(RUN) update $(if $(CONFIG),--config $(CONFIG),)

ai-sync:
	$(RUN) sync $(if $(CONFIG),--config $(CONFIG),)

ai-verify:
	$(RUN) verify --ci $(if $(CONFIG),--config $(CONFIG),)

ai-cost:
	$(RUN) cost-estimate $(if $(CONFIG),--config $(CONFIG),)