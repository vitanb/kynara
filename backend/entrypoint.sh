#!/bin/sh
set -e

# ── Pre-flight checks ─────────────────────────────────────────────────────────
if [ -z "$DATABASE_URL" ]; then
  echo "ERROR: DATABASE_URL is not set. Cannot run migrations." >&2
  exit 1
fi

if [ -z "$JWT_SECRET" ] || [ "$JWT_SECRET" = "CHANGE_ME_NOT_FOR_PRODUCTION_USE_32ch" ]; then
  echo "ERROR: JWT_SECRET is not set or is still the default. Set a strong secret." >&2
  exit 1
fi

# ── Migrations ────────────────────────────────────────────────────────────────
echo "[entrypoint] Running database migrations..."
alembic upgrade head
echo "[entrypoint] Migrations complete."

# ── Seed demo data (idempotent — skips if already present) ───────────────────
echo "[entrypoint] Seeding demo data..."
python -m app.scripts.seed

# ── Start server ──────────────────────────────────────────────────────────────
echo "[entrypoint] Starting uvicorn..."
exec uvicorn app.main:app --host "::" --port "${PORT:-8000}" --workers 2
