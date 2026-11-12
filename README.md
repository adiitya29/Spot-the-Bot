# Spot the Bot

A real-time multiplayer party game where 4–7 humans and 1 covert AI bot chat under random per-round aliases, then vote on who the bot is.

## Tech Stack

- **Backend**: Python 3.12+, Django 5.2+, Django REST Framework, Django Channels 4 (Redis), Daphne (ASGI), Celery 5, PostgreSQL 16, Redis 7
- **Frontend**: React, Vite, TypeScript (strict), Tailwind CSS, Zustand, TanStack Query, Framer Motion
- **Tooling**: Docker Compose, Nginx, pytest, Vitest, Playwright, ruff, ESLint, Prettier, GitHub Actions

## Quickstart (Local Docker)

```bash
cp .env.example .env
docker compose up --build
```

- Frontend (via Vite proxy): `http://localhost:5173`
- Backend health check: `http://localhost:8000/api/health/`

## Running Tests & Linters

### Backend

```bash
cd backend
ruff check .
ruff format --check .
pytest
```

### Frontend

```bash
cd frontend
npm run typecheck
npm run lint
npm run format:check
npm run test
```

## Documentation

See [`docs/PLAN.md`](docs/PLAN.md) for the full architecture and phased implementation specification.

