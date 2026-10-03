.PHONY: help install db backend frontend test lint

help:
	@echo "make install   - installa dipendenze backend e frontend"
	@echo "make db        - avvia PostgreSQL locale (docker compose)"
	@echo "make backend   - avvia API su http://localhost:8000 (docs: /docs)"
	@echo "make frontend  - avvia UI su http://localhost:5173"
	@echo "make test      - esegue i test"
	@echo "make lint      - esegue lint e type-check"

install:
	cd backend && python -m venv .venv && . .venv/bin/activate && pip install -e ".[dev]"
	cd frontend && npm install

db:
	docker compose up -d db

backend:
	cd backend && . .venv/bin/activate && uvicorn app.main:app --reload --port 8000

frontend:
	cd frontend && npm run dev

test:
	cd backend && . .venv/bin/activate && pytest

lint:
	cd backend && . .venv/bin/activate && ruff check . && ruff format --check .
	cd frontend && npm run lint
