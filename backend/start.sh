#!/bin/sh
# Startup script — converts DATABASE_URL, runs migrations, seeds super admin, starts server.
set -e

# Render provides postgres:// — SQLAlchemy asyncpg requires postgresql+asyncpg://
if [ -n "$DATABASE_URL" ]; then
  DATABASE_URL=$(echo "$DATABASE_URL" | sed 's|^postgres[^+]*://|postgresql+asyncpg://|')
  export DATABASE_URL
fi

echo ">> Running Alembic migrations..."
PYTHONPATH=/app alembic upgrade head

# Seed admin only if credentials are provided in environment.
# The script is idempotent — does nothing if an admin already exists.
if [ -n "$ADMIN_EMAIL" ] && [ -n "$ADMIN_PASSWORD" ]; then
  echo ">> Seeding admin..."
  PYTHONPATH=/app python scripts/seed.py || echo ">> Seed script exited with error — startup continues."
else
  echo ">> ADMIN_EMAIL / ADMIN_PASSWORD not set — skipping seed."
fi

echo ">> Starting JMJ Synergie API..."
exec uvicorn app.main:app \
  --host 0.0.0.0 \
  --port "${PORT:-8000}" \
  --workers "${WORKERS:-1}" \
  --proxy-headers \
  --forwarded-allow-ips "*"
