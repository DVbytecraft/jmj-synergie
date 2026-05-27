#!/bin/sh
# Startup script — converts DATABASE_URL and runs migrations before serving.
set -e

# Render provides postgres:// — SQLAlchemy asyncpg requires postgresql+asyncpg://
if [ -n "$DATABASE_URL" ]; then
  # Handle postgres://, postgresql://, and leave postgresql+asyncpg:// unchanged
  DATABASE_URL=$(echo "$DATABASE_URL" | sed 's|^postgres[^+]*://|postgresql+asyncpg://|')
  export DATABASE_URL
fi

echo ">> Running Alembic migrations..."
PYTHONPATH=/app alembic upgrade head

echo ">> Starting Biloz API..."
exec uvicorn app.main:app \
  --host 0.0.0.0 \
  --port "${PORT:-8000}" \
  --workers "${WORKERS:-4}" \
  --proxy-headers \
  --forwarded-allow-ips "*"
