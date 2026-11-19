#!/usr/bin/env bash
set -e

echo "==> Running database migrations..."
python manage.py migrate --noinput

echo "==> Seeding initial party game topics..."
python manage.py seed_topics || true

echo "==> Starting game phase scheduler in background..."
python manage.py run_scheduler &
SCHEDULER_PID=$!

echo "==> Starting Celery worker in background..."
celery -A config worker --loglevel=info -c 2 &
CELERY_PID=$!

cleanup() {
    echo "==> Shutting down background processes..."
    kill -TERM "$SCHEDULER_PID" "$CELERY_PID" 2>/dev/null || true
}
trap cleanup SIGTERM SIGINT

PORT="${PORT:-8000}"
echo "==> Starting Daphne ASGI server on port $PORT..."
exec daphne -b 0.0.0.0 -p "$PORT" config.asgi:application
