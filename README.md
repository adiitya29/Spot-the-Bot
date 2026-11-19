# Spot the Bot

> A real-time multiplayer social deduction party game where 4–7 human players and 1 covert AI bot chat under randomized per-round aliases, then vote on who the bot is.

[![CI](https://github.com/adiitya29/Spot-the-Bot/actions/workflows/ci.yml/badge.svg)](https://github.com/adiitya29/Spot-the-Bot/actions/workflows/ci.yml)
[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/release/python-3120/)
[![Django 5.2](https://img.shields.io/badge/django-5.2%20LTS-green.svg)](https://www.djangoproject.com/)
[![React 19](https://img.shields.io/badge/react-19-blue.svg)](https://react.dev/)
[![TypeScript](https://img.shields.io/badge/typescript-5.7%20strict-blue.svg)](https://www.typescriptlang.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## 1. Game Overview & Rules

In **Spot the Bot**, players join via a shared 6-character room code on their phones or computers without creating an account. During each round, everyone chats about a creative topic, but one of the participants is an AI bot specifically tuned to imitate human typing cadences, typo rates, lowercase slang, and casual hesitation.

```
       ┌─────────────┐
       │ Room Lobby  │  Host shares 6-char code; 4–7 humans join
       └──────┬──────┘
              │ Game Starts (3 rounds)
              ▼
       ┌─────────────┐
       │   ANSWER    │  45s: Everyone answers topic prompt under random alias
       └──────┬──────┘  (e.g., Teal Otter, Plum Falcon)
              ▼
       ┌─────────────┐
       │    CHAT     │  120s: Free-flowing live chat; Bot analyzes tone & latency
       └──────┬──────┘
              ▼
       ┌─────────────┐
       │    VOTE     │  30s: Select which alias you suspect is the AI bot
       └──────┬──────┘
              ▼
       ┌─────────────┐
       │   REVEAL    │  12s: Dramatic reveal animation, sound synthesis, scores
       └──────┬──────┘
              │ Next Round or Game Over
              ▼
       ┌─────────────┐
       │ Leaderboard │  Final scores, dynamic Pillow share cards & replays
       └─────────────┘
```

### Key Gameplay Rules:
- **Random Per-Round Aliases**: Real player nicknames are hidden during the round. Everyone appears as an alias (e.g. `Teal Otter`, `Plum Falcon`, `Sage Fox`). This prevents players from tracking the bot across rounds.
- **Zero Bot Leak Invariant**: The bot's identity (`is_bot`, `bot_seat_id`, `bot_alias`) is **strictly scrubbed** from all REST responses and WebSocket payloads until the reveal phase.
- **Scoring**:
  - `+100` points for correctly voting for the covert bot.
  - Round is marked `bot_fooled` when less than half of voting humans identify the bot.
  - Global deception statistics track overall bot survival across all matches.

---

## 2. Tech Stack

| Layer | Technologies |
| :--- | :--- |
| **Backend** | Python 3.12+, Django 5.2 LTS, Django REST Framework, Django Channels 4 (Redis Channel Layer), Daphne (ASGI), Celery 5, Celery Beat |
| **Frontend** | React 19, TypeScript (strict), Vite 6, Tailwind CSS, Zustand, TanStack Query, Framer Motion, Web Audio API |
| **Datastores** | PostgreSQL 16, Redis 7 (pub/sub channel layer, state cache & Celery broker) |
| **Image & Social** | Pillow 11+ dynamic PNG share cards, server-rendered Open Graph tags (`/s/<code\>/`) |
| **Testing** | pytest, pytest-django, pytest-asyncio, factory-boy, freezegun, Vitest, React Testing Library, Playwright E2E |
| **Code Quality** | Ruff (lint & format), ESLint, Prettier, strict TypeScript |
| **Production** | Multi-stage Dockerfiles, Nginx (HTTP/2, gzip, WebSocket upgrades), Sentry SDK, `python-json-logger`, k6 |

---

## 3. Architecture & Protocol

```
Mobile & Desktop Browsers
        │ (HTTPS / WSS)
        ▼
   [ Nginx ]  ─── Reverse proxy, gzip, SSL termination, static SPA cache
        │
   ┌────┴──────────────────────────┐
   │ (REST API & WebSockets)       │ (Static files & Open Graph tags)
   ▼                               ▼
[ Daphne ASGI Server ]       [ /dist HTML / CSS / JS ]
   │
   ├── Django ORM  ───────────────►  [ PostgreSQL 16 ]
   ├── Channels Channel Layer  ───►  [ Redis 7 ]
   └── Celery Task Dispatch  ─────►  [ Celery Worker & Beat ]
                                           │
                                     [ LLM Bot Engine ]
                                     (Gemini / Anthropic / Fake)
```

### WebSocket Protocol Design:
- **Transport**: Persistent WebSocket connection to `/ws/room/<code\>/?token=<player_token\>`.
- **Sequencing & Resiliency**: All server broadcasts include a monotonic sequence number (`seq`). Clients detect sequence gaps and reconnect with exponential backoff and jitter.
- **Idempotency**: Chat events contain `client_msg_id` for duplicate suppression.
- **Duplicate Tab Eviction**: Connecting a duplicate tab with the same token evicts the older socket with close code `4001`.
- **Clock Synchronization**: Server-provided timestamp headers calibrate local timers to ensure synchronized countdown clocks across all participants.

---

## 4. Quickstart (Local Development)

### Prerequisites:
- [Docker](https://docs.docker.com/get-docker/) & [Docker Compose](https://docs.docker.com/compose/)
- Optional: Node 22+ and Python 3.12+ for local editing outside containers.

### 1. Clone & Configure:
```bash
git clone https://github.com/adiitya29/Spot-the-Bot.git
cd Spot-the-Bot
cp .env.example .env
```

### 2. Launch Docker Services:
```bash
docker compose up --build
```

### 3. Open the Application:
- **Frontend App**: [http://localhost:5173](http://localhost:5173)
- **Backend Healthcheck**: [http://localhost:8000/api/health/](http://localhost:8000/api/health/)
- **Match Replays**: [http://localhost:5173/replays](http://localhost:5173/replays)

---

## 5. Testing & Code Quality

Spot the Bot maintains comprehensive automated test suites covering 100% of the game state machine, bot persona engine, viral replays, and UI flows.

### Running Backend Tests (116 tests):
```bash
docker compose exec -T backend sh -c "ruff check . && ruff format --check . && pytest"
```

### Running Frontend Tests (36 tests):
```bash
docker compose exec -T frontend npm run format:check
docker compose exec -T frontend npm run lint
docker compose exec -T frontend npm run typecheck
docker compose exec -T frontend npm run test -- --run
```

### Running Playwright E2E Tests:
```bash
cd frontend
npm run test:e2e
```

---

## 6. Performance & k6 WebSocket Load Testing

A dedicated k6 load test script ([scripts/loadtest.js](scripts/loadtest.js)) benchmarks WebSocket fan-out latency across **100 concurrent rooms** and **600 active clients**.

```bash
# Run k6 load test against running stack
k6 run scripts/loadtest.js -e ROOMS=100 -e CLIENTS=6
```

### Benchmark Results:
- **Target Invariant**: p95 WebSocket fan-out latency $< 150\text{ ms}$
- **Measured Result**: **$38.4\text{ ms}$** ($\approx 3.9\times$ headroom)
- **Message Delivery Success**: **100.0%** (zero message drops)
- Full analysis available in [`docs/eval/loadtest_report.md`](docs/eval/loadtest_report.md).

---

## 7. Production Hardening & Deployment

### Production Docker Compose Stack:
Launch the hardened production stack using [docker-compose.prod.yml](docker-compose.prod.yml):

```bash
docker compose -f docker-compose.prod.yml up --build -d
```

### Security Checklist:
- [x] **`DEBUG = False`** enforced in `config.settings.prod`.
- [x] **Strict Secret Key**: Refuses startup without valid `DJANGO_SECRET_KEY`.
- [x] **SSL & Proxy Headers**: `SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")` and `SECURE_SSL_REDIRECT = True`.
- [x] **Cookie Security**: `SESSION_COOKIE_SECURE = True`, `CSRF_COOKIE_SECURE = True`, `SameSite = "Lax"`.
- [x] **HSTS**: `SECURE_HSTS_SECONDS = 31536000` with subdomains and preload.
- [x] **Proxy IP Resolution**: `NUM_PROXIES = 1` for accurate DRF rate throttling behind Nginx.
- [x] **Non-Root Containers**: Backend runs under unprivileged `appuser` (UID 1000).
- [x] **Zero Bot Identity Leakage**: Verified by automated defense-in-depth security scanners (`test_no_bot_leak.py`).
- [x] **Structured JSON Logging**: Handled via `python-json-logger` for automated log aggregation (Datadog, CloudWatch, GCP Cloud Logging).
- [x] **Sentry Error Tracking**: Full Django, Celery, and Redis integration.

---

## 8. Environment Variables Reference

| Variable | Default | Description |
| :--- | :--- | :--- |
| `DJANGO_SETTINGS_MODULE` | `config.settings.dev` | Settings module (`config.settings.dev` or `config.settings.prod`) |
| `DJANGO_SECRET_KEY` | `dev-insecure-key` | Cryptographic secret for signing sessions and tokens |
| `ALLOWED_HOSTS` | `localhost,127.0.0.1` | Comma-separated list of valid host headers |
| `DATABASE_URL` | `postgres://...` | PostgreSQL connection URI |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection URI for Channels & Cache |
| `CELERY_BROKER_URL` | `redis://localhost:6379/1` | Redis broker URI for Celery tasks |
| `FRONTEND_ORIGIN` | `http://localhost:5173` | Allowed frontend origin for CORS/CSRF |
| `CSRF_TRUSTED_ORIGINS` | Auto-configured | Trusted origins for CSRF POST requests |
| `NUM_PROXIES` | `1` | Number of reverse proxies in front of Daphne (for IP resolution) |
| `LLM_PROVIDER` | `fake` | LLM provider: `fake`, `gemini`, `anthropic`, or `openai` |
| `LLM_API_KEY` | `""` | API key for LLM provider |
| `LLM_MODEL` | `gemini-2.0-flash` | Model identifier string |
| `BOT_ENABLED` | `True` | Toggle bot engine generation |
| `SENTRY_DSN` | `""` | Sentry project DSN for error reporting |
| `SECURE_SSL_REDIRECT` | `True` (prod) | Force HTTPS redirection |

---

## 9. Development Status

All Phase 0 through Phase 9 milestones have been completed and verified.
