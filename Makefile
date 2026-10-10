.PHONY: help lock docker-build docker-run infra-fmt infra-validate infra-test install db migrate seed demo migration mail mail-test backend frontend test lint api-types

help:
	@echo "make install   - installa dipendenze backend e frontend"
	@echo "make db        - avvia PostgreSQL locale (docker compose)"
	@echo "make migrate   - applica le migrazioni al database locale"
	@echo "make seed      - carica profili, tariffe 2026 e festività (idempotente)"
	@echo "make demo       - carica dati di esempio con l'admin di BOOTSTRAP_ADMIN_EMAIL (serve il backend acceso)"
	@echo "make lock       - rigenera i file delle versioni esatte (immagine, sviluppo e CI)"
	@echo "make docker-build - costruisce l'immagine; make docker-run la avvia su http://localhost:8080"
	@echo "make infra-fmt | infra-validate | infra-test - controlli di Terraform"
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

lock:
	rm -rf /tmp/ce-lock-env && python3 -m venv /tmp/ce-lock-env
	python3 -c "import tomllib; print('\n'.join(tomllib.load(open('backend/pyproject.toml','rb'))['project']['dependencies']))" > /tmp/ce-lock-in.txt
	/tmp/ce-lock-env/bin/pip install -q -r /tmp/ce-lock-in.txt
	{ echo "# Versioni esatte delle dipendenze di produzione (generato da: make lock). Non modificare a mano."; /tmp/ce-lock-env/bin/pip freeze --exclude pip --exclude setuptools --exclude wheel | sort -f; } > backend/requirements.lock
	/tmp/ce-lock-env/bin/pip install -q pytest httpx ruff pypdf
	{ echo "# Versioni esatte per sviluppo e CI: produzione + strumenti di prova (generato da: make lock). Non modificare a mano."; /tmp/ce-lock-env/bin/pip freeze --exclude pip --exclude setuptools --exclude wheel | sort -f; } > backend/requirements-dev.lock
	@echo "Aggiornati backend/requirements.lock e backend/requirements-dev.lock. Se le versioni sono cambiate lancia anche: make api-types"

docker-build:
	docker build -t ce-portal .

docker-run:
	docker run --rm -p 8080:8080 -e APP_ENV=local ce-portal

infra-fmt:
	terraform fmt -recursive infra/terraform

infra-validate:
	@for d in modules/ce_portal envs/test envs/prod; do echo "== $$d"; terraform -chdir=infra/terraform/$$d init -backend=false -input=false >/dev/null && terraform -chdir=infra/terraform/$$d validate || exit 1; done

infra-test:
	terraform -chdir=infra/terraform/modules/ce_portal init -backend=false -input=false >/dev/null
	terraform -chdir=infra/terraform/modules/ce_portal test
