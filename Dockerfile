# Immagine unica per test e produzione: backend FastAPI + frontend compilato.
# La configurazione (ambiente, database, segreti, Client ID di Google) arriva a runtime da Cloud Run.
#
#   docker build -t ce-portal .
#   docker run --rm -p 8080:8080 -e APP_ENV=local ce-portal

# ---------------------------------------------------------------- 1. frontend
FROM node:22-alpine AS frontend
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# ---------------------------------------------------------------- 2. immagine finale
FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app

# Le dipendenze (versioni esatte) si installano a parte dal codice: il livello si riusa finché il file non cambia.
COPY backend/requirements.lock /tmp/requirements.lock
RUN pip install -r /tmp/requirements.lock && rm /tmp/requirements.lock

COPY backend/app ./app
COPY backend/migrations ./migrations
COPY backend/alembic.ini ./
COPY --from=frontend /build/dist ./static

ENV STATIC_DIR=/app/static \
    APP_ENV=prod
RUN useradd --system --uid 10001 --no-create-home app && chown -R app /app
USER app

EXPOSE 8080
# Cloud Run indica la porta in $PORT. I lavori (migrazioni, email, dati iniziali) usano la stessa immagine
# con un altro comando: alembic upgrade head · python -m app.notifications dispatch · python -m app.db.seed
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080} --proxy-headers --forwarded-allow-ips='*'"]
