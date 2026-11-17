# DAHA — developer commands (PLAN.md §5.5). Run from the repo root.
# uv and Docker Desktop install their CLIs here; harmless if they're already on PATH.
export PATH := $(HOME)/.local/bin:$(HOME)/.docker/bin:$(PATH)

.PHONY: db migrate seed api web test smoke reindex lan up

db:  ## start Postgres (+pgvector) and wait until healthy
	docker compose up -d --wait db

migrate:  ## create / update tables
	cd backend && uv run alembic upgrade head

seed:  ## reset and load the demo data (deterministic)
	cd backend && uv run python -m app.seed.seed --reset

api:  ## backend on http://localhost:8000 (docs at /docs)
	cd backend && uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

web:  ## web app on http://localhost:3000
	cd web && pnpm dev --hostname 0.0.0.0

test:  ## backend pytest + ruff, web lint + typecheck
	cd backend && uv run ruff check . && uv run pytest -q
	@if [ -f web/package.json ]; then cd web && pnpm lint && pnpm typecheck; fi

smoke:  ## end-to-end API smoke test (A4) against a running `make api`
	cd backend && uv run python scripts/smoke_api.py

reindex:  ## recompute embeddings (C)
	cd backend && uv run python -c "from app.discovery.hooks import reindex_all; print(reindex_all(), 'rows reindexed')"

lan:  ## print this laptop's LAN address for testing on a phone
	@ip=$$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || hostname -I 2>/dev/null | awk '{print $$1}'); \
	echo "Phone on the same Wi-Fi: http://$$ip:3000"

up:  ## full stack in Docker (A5 — not built yet)
	@echo "make up arrives with A5 (after the hackathon). Use: make db migrate seed api"
