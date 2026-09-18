.PHONY: setup dev test lint format incident investigate evaluate benchmark reset clean

setup: ## Install Python and Node dependencies for local (non-Docker) development.
	uv sync
	cd apps/web && npm install

dev: ## Start the full stack via Docker Compose.
	docker compose up --build

test: ## Run the Python test suite.
	uv run pytest

lint: ## Lint Python (ruff) and the web app (eslint).
	uv run ruff check .
	cd apps/web && npm run lint

format: ## Format Python (ruff format) and check it's applied.
	uv run ruff format .

reset: ## Stop and remove containers + volumes (drops the local Postgres data).
	docker compose down -v

clean: reset ## Remove local build/dependency artifacts.
	rm -rf .venv apps/web/node_modules apps/web/.next .pytest_cache .ruff_cache

incident: ## Generate a reproducible incident: make incident SCENARIO=db_connection_pool
	@test -n "$(SCENARIO)" || (echo "Usage: make incident SCENARIO=<id> (e.g. db_connection_pool)"; exit 1)
	uv run python -m simulator.replay --scenario $(SCENARIO)

investigate: ## Run a full investigation: make investigate INCIDENT=INC-0001
	@test -n "$(INCIDENT)" || (echo "Usage: make investigate INCIDENT=<id> (e.g. INC-0001)"; exit 1)
	uv run python -m orchestration.graph --incident $(INCIDENT)

evaluate: benchmark ## Alias for `make benchmark` — spec lists both, this project has one evaluation runner.

benchmark: ## Run the evaluation benchmark (direct-LLM vs single-agent vs multi-agent).
	uv run python -m evaluation.reports
