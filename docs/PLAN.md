# Spot the Bot — Implementation Plan

An agent-ready build spec for a Django + React multiplayer party game where one chat participant is an AI pretending to be human.

## 0. How to use this document (instructions for the coding agent)

- Read the whole document first, then work one phase at a time (Section 11). Do not start a phase until the previous one passes its acceptance criteria.
- At the start of each phase, restate its goal and list the files you will create or change. At the end, run lint and tests, summarize the diff, and stop for human review.
- Write tests alongside code. The state machine, scoring and every bot module need unit tests before you move on.
- Do not add libraries outside Section 2 without saying why. Use Python type hints and strict TypeScript. Keep modules small and single-purpose.
- If a requirement is ambiguous, ask instead of guessing.
- **Non-negotiable**: the bot’s identity must never appear in any REST response or WebSocket payload before the REVEAL phase (Section 5, rule 1).
- Commit after each completed task using Conventional Commits.

## 1. Product summary

Players open a shared link, join a room with only a nickname, and chat about a topic. Among the participants is one AI bot that imitates a human by matching the room’s typing style, slang and pacing. After the chat, everyone votes on who the bot is. The reveal is the big moment, and the shareable outputs are a result card and a replay.

### Rules

- **Room code**: 6 characters from an unambiguous alphabet (no `I`, `O`, `0`, `1`). The creator is the host.
- **Seats**: 4–7 humans plus 1 bot. The minimum number of humans is configurable (default 4, allow 3 in development). Nobody can join after the game starts.
- **Identity**: guests only. Nickname 2–20 characters, unique within the room. No accounts in v1.
- **Aliases**: during a round, every participant (humans and bot) appears under a random per-round alias such as `Teal Otter`. Real nicknames are shown only in the lobby and at the reveal. This stops players from spotting the bot by name and from tracking it across rounds.
- **Game**: 3 rounds by default. Each round has a topic and these phases: `ANSWER` (45 s), `CHAT` (120 s), `VOTE` (30 s), `REVEAL` (12 s). All durations are configurable per room.
- **Scoring**: `+100` for each correct vote. A round counts as `bot_fooled` when fewer than half of the voting humans picked the bot; this feeds a public statistic.

## 2. Tech stack

- **Backend**: Python 3.12+, Django 5.2 LTS or newer, Django REST Framework, Django Channels 4 with `channels-redis`, served by Daphne (ASGI), Celery 5 (Redis broker) plus Celery beat, PostgreSQL 16, Redis 7, `psycopg` 3, `django-environ`, `Pillow`, `httpx`, `sentry-sdk`, `python-json-logger`. Testing: `pytest`, `pytest-django`, `pytest-asyncio`, `factory_boy`, `freezegun`.
- **Frontend**: React + Vite + TypeScript (strict), React Router, Zustand, TanStack Query, Tailwind CSS, Framer Motion, Vitest + React Testing Library, Playwright, ESLint + Prettier.
- **Infra and tooling**: Docker and Docker Compose, Nginx, GitHub Actions, `ruff`, `pre-commit`, `k6`, Sentry.
- **LLM access**: Provider-agnostic `LLMClient` interface with `FakeLLMClient` for tests/offline dev and one real provider via env vars.

## 3. Repository structure

Matches `backend/`, `frontend/`, `docker/`, `scripts/`, `docs/`, `docker-compose.yml`, `.env.example`.

## 4–16. Architecture, Data Model, Protocol, Bot Engine, Phases 0–9, Testing, Security & DoD

Refer to the full engineering specification and phased roadmap tracked in the project plan.

