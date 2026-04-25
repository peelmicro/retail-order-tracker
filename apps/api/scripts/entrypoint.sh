#!/bin/sh
# Container entrypoint: run Alembic migrations, then exec uvicorn.
#
# Postgres readiness is guaranteed by the docker-compose `depends_on` with
# `condition: service_healthy`, so we don't loop here. If migrations ever
# flake on slow machines, add a retry around alembic.

set -e

echo "==> Running database migrations"
.venv/bin/alembic upgrade head

echo "==> Starting FastAPI on 0.0.0.0:8000"
exec .venv/bin/fastapi run src/main.py --host 0.0.0.0 --port 8000
