SHELL := bash
.SHELLFLAGS := -eu -o pipefail -c
.DEFAULT_GOAL := help
MAKEFLAGS += --no-print-directory

RUN := .run
API_URL := http://127.0.0.1:8000/openapi.json
WEB_URL := http://127.0.0.1:5173/

.PHONY: help install format up down restart status logs services migrate ingest index ask eval eval-retrieval eval-draft \
	ci lockfile lint secrets typecheck test audit build web-check evals e2e check-all

SOURCE ?= all
CLI := uv run python -m rag_stack.cli

help: ## Show this help
	@awk 'BEGIN {FS = ":.*## "} /^[a-z0-9-]+:.*## / {printf "  \033[1m%-10s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)
	@echo
	@echo "  Deleting all stored conversations is manual: make down && docker compose down -v"

# --- Setup ---------------------------------------------------------------------------------

install: ## Install Python and web dependencies; create .env from the example if missing
	uv sync
	npm ci --prefix web
	@[ -f .env ] || { cp .env.example .env && echo "Created .env: it uses the sub2api gateway; see it for other LLM providers"; }

format: ## Fix lint issues and format Python code
	uv run ruff check --fix
	uv run ruff format

# --- Run the app ---------------------------------------------------------------------------

# A PID file holds "<process group ID> <start time> <boot ID>". Start time (field 22 of
# /proc/<pid>/stat) plus boot ID identify the process exactly, so a stale file whose ID was
# reused (after a reboot or a crash) never matches an unrelated process.
identity = echo "$(1) $$(sed 's/.*) //' /proc/$(1)/stat | cut -d' ' -f20) $$(cat /proc/sys/kernel/random/boot_id)"

# ours <name>: true, with $$pgid set, if the PID file names our still-running process group
ours = { read -r pgid _ 2>/dev/null < $(RUN)/$(1).pid \
	&& [ "$$({ $(call identity,$$pgid); } 2>/dev/null)" = "$$(cat $(RUN)/$(1).pid)" ]; }

# start <name>,<url>,<command>: run in a new process group (PID file = group ID), log to .run/
define start
	@if $(call ours,$(1)); then \
		echo "$(1): already running"; \
	elif ! { curl -s -o /dev/null --max-time 2 $(2); [ $$? -eq 7 ]; }; then \
		echo "$(1): another process is using the port of $(2)" >&2; exit 1; \
	else \
		setsid bash -c '$(3)' > $(RUN)/$(1).log 2>&1 < /dev/null & \
		$(call identity,$$!) > $(RUN)/$(1).pid; \
		echo "$(1): starting (log: $(RUN)/$(1).log)"; \
	fi
endef

# wait_for <name>,<url>: until the URL answers; show the log if the process dies or 30s pass
define wait_for
	@deadline=$$((SECONDS + 30)); \
	while (( SECONDS < deadline )); do \
		if ! $(call ours,$(1)); then \
			echo "$(1): exited during startup. Last log lines:" >&2; tail -n 20 $(RUN)/$(1).log >&2; exit 1; \
		fi; \
		curl -fs -o /dev/null --max-time 2 $(2) && exit 0; \
		sleep 0.5; \
	done; \
	echo "$(1): not ready after 30s. Last log lines:" >&2; tail -n 20 $(RUN)/$(1).log >&2; exit 1
endef

# stop <name>: SIGTERM the process group, SIGKILL if it hasn't exited after 10s
define stop
	@if $(call ours,$(1)); then \
		kill -- -$$pgid 2>/dev/null || true; \
		for i in $$(seq 20); do kill -0 -- -$$pgid 2>/dev/null || break; sleep 0.5; done; \
		kill -9 -- -$$pgid 2>/dev/null || true; \
		echo "$(1): stopped"; \
	else \
		echo "$(1): not running"; \
	fi; \
	rm -f $(RUN)/$(1).pid
endef

services: ## Start Postgres and Qdrant and wait until they are healthy
	docker compose up -d --wait

up: services ## Start everything: Docker services, API (:8000) and web UI (:5173)
	@mkdir -p $(RUN)
	$(call start,api,$(API_URL),exec uv run uvicorn rag_stack.api.app:create_app --factory --reload --host 127.0.0.1 --port 8000)
	$(call start,web,$(WEB_URL),cd web && exec npm run dev -- --host 127.0.0.1 --port 5173 --strictPort)
	$(call wait_for,api,$(API_URL))
	$(call wait_for,web,$(WEB_URL))
	@echo "Ready: open http://localhost:5173"

down: ## Stop the API, the web UI and the Docker services (stored data is kept)
	$(call stop,web)
	$(call stop,api)
	docker compose down

restart: ## Stop everything, then start it again
	@$(MAKE) down
	@$(MAKE) up

status: ## Show what is running
	@if $(call ours,api); then echo "api: running (process group $$pgid)"; else echo "api: stopped"; fi
	@if $(call ours,web); then echo "web: running (process group $$pgid)"; else echo "web: stopped"; fi
	@docker compose ps --format 'table {{.Service}}\t{{.Status}}\t{{.Ports}}'

logs: ## Follow the API and web UI logs
	tail -n 50 -f $(RUN)/api.log $(RUN)/web.log

# --- Knowledge base ------------------------------------------------------------------------

migrate: services ## Create or upgrade our Postgres tables (the edge table)
	uv run alembic upgrade head

ingest: ## Fetch, snapshot and chunk sources: make ingest SOURCE=<id|all> (unchanged ones are skipped)
	$(CLI) ingest $(SOURCE)

index: migrate ## Embed processed chunks into Qdrant and load edges: make index SOURCE=<id|all>
	$(CLI) index $(SOURCE)

ask: ## Answer one question from the knowledge base: make ask Q="What is AML.T0051?"
	@[ -n "$(Q)" ] || { echo 'Usage: make ask Q="your question"' >&2; exit 1; }
	$(CLI) ask "$(Q)"

eval: ## The paid eval run (~150 LLM calls): golden set vs. the baseline, writes report.md
	$(CLI) eval

eval-retrieval: ## Retrieval scores and latency, no LLM calls: make eval-retrieval [SPLIT=dev|test]
	$(CLI) eval --retrieval-only --split $(or $(SPLIT),dev)

eval-draft: ## Draft test questions into drafts.jsonl for review: make eval-draft SOURCE=<id> CATEGORY=<c> [N=5]
	$(CLI) eval-draft $(SOURCE) $(CATEGORY) -n $(or $(N),5)

# --- Checks (same order as .github/workflows/ci.yml) -----------------------------------------

ci: lockfile lint secrets typecheck test audit build web-check ## Run the CI pipeline locally
	@echo "Local CI passed"

lockfile:
	uv lock --check

lint: ## Lint and check formatting
	uv run ruff check
	uv run ruff format --check

secrets: ## Scan the git history for secrets
	gitleaks git --redact --exit-code 1 .

typecheck: ## Type-check with pyright
	uv run pyright

test: ## Run unit tests
	uv run pytest tests/unit

audit: ## Audit dependencies for known vulnerabilities
	@req=$$(mktemp); trap 'rm -f $$req' EXIT; \
	uv export --frozen --no-emit-project --format requirements-txt > $$req; \
	uvx pip-audit -r $$req --disable-pip

build: ## Build the Python package
	uv build

web-check: ## Lint, test and build the web UI
	npm run --prefix web lint
	npm test --prefix web -- --run
	npm run --prefix web build

evals: ## AI tests: thresholds on the saved `make eval` results (fails if stale) + injection (1 call)
	uv run pytest tests/ai

e2e: migrate ## Run end-to-end tests (real Postgres, Qdrant and LLM)
	uv run pytest tests/e2e

check-all: ci eval evals e2e ## CI, one paid eval run, AI tests and e2e: the definition of done
	@echo "All checks passed"
