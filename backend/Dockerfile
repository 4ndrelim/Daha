# DAHA backend: FastAPI on :8000. Build from the repo root or from backend/:
#   docker build -t daha-api backend
FROM python:3.12-slim AS base

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"
WORKDIR /app

# Dependencies first, so code changes don't reinstall them.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY . .

# Never run as root. The data folders are volumes in docker-compose.
RUN useradd --create-home --uid 10001 daha \
    && mkdir -p /app/uploads /app/.fastembed_cache \
    && chown -R daha:daha /app/uploads /app/.fastembed_cache
USER daha

EXPOSE 8000
HEALTHCHECK --interval=5s --timeout=3s --start-period=60s --retries=30 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health')"

# One worker: scans and matching run as in-process background tasks, and the HarnessRouter
# concurrency limit is per process (docs/decisions.md).
CMD ["sh", "docker-entrypoint.sh"]
