FROM python:3.10-slim AS backend

RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc python3-dev curl \
    && rm -rf /var/lib/apt/lists/*

# Install poetry (no virtualenvs inside container)
RUN pip install --no-cache-dir poetry \
    && poetry config virtualenvs.create false

WORKDIR /app

# Copy dependency files first (cache layer)
COPY pyproject.toml poetry.lock* ./
RUN poetry install --no-interaction --no-ansi --only main --no-root

# Copy .env.example as fallback (compose.yaml mounts the real .env)
COPY .env.example /app/.env.example

COPY apps/ apps/

RUN mkdir -p apps/backend/data/cache apps/backend/logs

EXPOSE 5001

HEALTHCHECK --interval=30s --timeout=10s --retries=3 --start-period=20s \
    CMD curl -f http://localhost:5001/api/health || exit 1

CMD ["uvicorn", "apps.backend.api.app:asgi_app", "--host", "0.0.0.0", "--port", "5001"]
