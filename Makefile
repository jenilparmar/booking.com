.PHONY: setup migrate generate-sample import-sample backend frontend test lint build check

setup:
	cd backend && uv sync
	cd frontend && npm install
	cd backend && uv run python -m app.cli migrate

migrate:
	cd backend && uv run python -m app.cli migrate

generate-sample:
	cd backend && uv run python ../data/generate_sample.py

import-sample:
	cd backend && uv run python -m app.cli import ../data/sample_reviews.csv --source synthetic

backend:
	cd backend && uv run uvicorn app.main:app --reload --port 8000

frontend:
	cd frontend && npm run dev

test:
	cd backend && uv run pytest
	cd frontend && npm test

lint:
	cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy app
	cd frontend && npm run lint && npm run typecheck

build:
	cd frontend && npm run build

check: lint test build
