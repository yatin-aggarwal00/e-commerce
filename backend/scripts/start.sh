#!/usr/bin/env bash
# Container entrypoint: wait for Postgres, apply migrations, seed (dev), serve.
set -euo pipefail

echo "Waiting for database..."
python - <<'PY'
import os, time
from sqlalchemy import create_engine, text

url = os.environ.get("DATABASE_URL", "postgresql+psycopg2://postgres:postgres@db:5432/furniture")
for attempt in range(30):
    try:
        create_engine(url).connect().execute(text("SELECT 1"))
        print("Database is ready.")
        break
    except Exception as exc:
        print(f"  not ready ({attempt+1}/30): {exc}")
        time.sleep(2)
else:
    raise SystemExit("Database never became ready")
PY

echo "Running migrations..."
alembic upgrade head

if [ "${SEED_ON_START:-false}" = "true" ]; then
  echo "Seeding demo data..."
  python -m app.seed || true
fi

echo "Starting API..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers "${WEB_CONCURRENCY:-2}"
