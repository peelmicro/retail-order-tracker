# syntax=docker/dockerfile:1.7
#
# Build context is the repository root (see docker-compose.yml). This lets
# the Dockerfile COPY both apps/api/* and the top-level samples/ directory
# into the image — the seed endpoint needs the sample files at runtime.

# Base image registry. Defaults to Google's transparent Docker Hub mirror
# (mirror.gcr.io/library) for two reasons:
#
# 1. Docker Hub anonymous pulls are rate-limited (100 per 6h per IP).
#    mirror.gcr.io has no such limit.
# 2. Docker Hub serves image blobs from r2.cloudflarestorage.com which is
#    intermittently blocked by Spanish ISPs during LaLiga matches (court-
#    ordered Cloudflare IP-range blocks against piracy; collateral damage
#    to Docker Hub, GitHub, ChatGPT, Vercel, etc.).
#
# Same image, same layer SHAs — just a different CDN. To pull from Docker
# Hub directly, set BASE_REGISTRY=docker.io/library in your .env or pass
#   docker compose build --build-arg BASE_REGISTRY=docker.io/library
ARG BASE_REGISTRY=mirror.gcr.io/library
FROM ${BASE_REGISTRY}/python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

# uv at build time only — runtime uses .venv/bin/* directly.
RUN pip install --no-cache-dir uv

WORKDIR /app

# Install Python deps into /app/.venv
COPY apps/api/requirements.txt .
RUN uv venv && uv pip install --no-cache -r requirements.txt

# Application source
COPY apps/api/src/ ./src/
COPY apps/api/alembic/ ./alembic/
COPY apps/api/alembic.ini ./
COPY apps/api/pytest.ini ./

# Sample order files used by POST /api/seed
COPY samples/ ./samples/

# Entrypoint
COPY apps/api/scripts/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=5s --start-period=20s --retries=5 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health').read()" || exit 1

ENTRYPOINT ["/entrypoint.sh"]
