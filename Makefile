.PHONY: up down test logs shell licenses help

COMPOSE = cd deploy && docker compose

# Start all services (persistence, orchestration, inference, harness).
up:
	$(COMPOSE) up -d

# Stop all services (data volumes are preserved).
down:
	$(COMPOSE) down

# Run the full test suite (no containers required).
test:
	uv run --extra dev pytest tests/ -v

# Tail logs from all services.
logs:
	$(COMPOSE) logs -f

# Open a Python REPL with the harness package on the path.
shell:
	uv run python

# Audit installed dependency licenses (Doc 8 standing duty).
licenses:
	uv run --extra dev pip-licenses --order=license --format=markdown

help:
	@echo "Targets: up  down  test  logs  shell  licenses"
