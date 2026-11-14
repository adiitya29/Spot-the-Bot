# Multi-stage Dockerfile for Spot the Bot backend
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libjpeg62-turbo-dev \
    zlib1g-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Stage: Development (with dev requirements for pytest, ruff, factory-boy)
FROM base AS dev
COPY backend/requirements.txt backend/requirements-dev.txt ./
RUN pip install --upgrade pip && pip install -r requirements-dev.txt
COPY backend/ ./
EXPOSE 8000
CMD ["daphne", "-b", "0.0.0.0", "-p", "8000", "config.asgi:application"]

# Stage: Production (hardened, minimal production requirements, non-root user)
FROM base AS prod
RUN useradd -m -u 1000 appuser

COPY backend/requirements.txt ./
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY backend/ ./
RUN chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health/', timeout=3)" || exit 1

CMD ["daphne", "-b", "0.0.0.0", "-p", "8000", "config.asgi:application"]
