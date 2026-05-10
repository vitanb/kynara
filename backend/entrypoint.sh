#!/bin/sh
set -e

echo "Running database migrations..."
alembic upgrade head

echo "Seeding demo data (skipped if already present)..."
python -m app.scripts.seed

echo "Starting server..."
exec uvicorn app.main:app --host "::" --port 8000 --workers 2
