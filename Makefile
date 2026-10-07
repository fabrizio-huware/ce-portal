.PHONY: help install db migrate seed demo migration mail mail-test backend frontend test lint api-types

help:
	@echo "make install   - installa dipendenze backend e frontend"
	@echo "make db        - avvia PostgreSQL locale (docker compose)"
	@echo "make migrate   - applica le migrazioni al database locale"
	@echo "make seed      - carica profili, tariffe 2026 e festività (idempotente)"
	@echo "make demo       - carica dati di esempio con l'admin di BOOTSTRAP_ADMIN_EMAIL (serve il backend acceso)"
	@echo "make api-types  - rigenera i tipi TypeScript dal backend"
	@echo "make migration m=\"descrizione\" - genera una nuova migrazione dai modelli"
	@echo "make mail       - invia le email in coda (lo stesso comando del job periodico)"
	@echo "make mail-test to=tua@email - invia un'email di prova"
	@echo "make backend   - avvia API su http://localhost:8000 (docs: /docs)"
	@echo "make frontend  - avvia UI su http://localhost:5173"
	@echo "make test      - esegue i test"
	@echo "make lint      - esegue lint e type-check"

install:
	cd backend && python3 -m venv .venv && . .venv/bin/activate && pip install -e ".[dev]"
	cd frontend && npm install

db:
	docker compose up -d db

migrate:
	@test -d backend/.venv || { echo "Ambiente Python mancante: esegui prima  make install"; exit 1; }
	cd backend && . .venv/bin/activate && alembic upgrade head

seed:
	@test -d backend/.venv || { echo "Ambiente Python mancante: esegui prima  make install"; exit 1; }
	cd backend && . .venv/bin/activate && python -m app.db.seed

migration:
	@test -d backend/.venv || { echo "Ambiente Python mancante: esegui prima  make install"; exit 1; }
	cd backend && . .venv/bin/activate && alembic revision --autogenerate -m "$(m)"

demo:
	@test -d backend/.venv || { echo "Ambiente Python mancante: esegui prima  make install"; exit 1; }
	cd backend && . .venv/bin/activate && python scripts/seed_demo.py

api-types:
	@test -d backend/.venv || { echo "Ambiente Python mancante: esegui prima  make install"; exit 1; }
	cd backend && . .venv/bin/activate && python -c "import json; from app.main import app; json.dump(app.openapi(), open('../frontend/openapi.json','w'), indent=1, ensure_ascii=False)"
	cd frontend && npm run gen:api

mail:
	@test -d backend/.venv || { echo "Ambiente Python mancante: esegui prima  make install"; exit 1; }
	cd backend && . .venv/bin/activate && python -m app.notifications dispatch

mail-test:
	@test -d backend/.venv || { echo "Ambiente Python mancante: esegui prima  make install"; exit 1; }
	cd backend && . .venv/bin/activate && python -m app.notifications send-test "$(to)"

backend:
	@test -d backend/.venv || { echo "Ambiente Python mancante: esegui prima  make install"; exit 1; }
	cd backend && . .venv/bin/activate && uvicorn app.main:app --reload --port 8000

frontend:
	cd frontend && npm run dev

test:
	@test -d backend/.venv || { echo "Ambiente Python mancante: esegui prima  make install"; exit 1; }
	cd backend && . .venv/bin/activate && pytest

lint:
	@test -d backend/.venv || { echo "Ambiente Python mancante: esegui prima  make install"; exit 1; }
	cd backend && . .venv/bin/activate && ruff check . && ruff format --check .
	cd frontend && npm run lint
