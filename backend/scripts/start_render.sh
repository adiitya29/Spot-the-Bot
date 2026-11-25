#!/usr/bin/env bash
set -e

echo "==> Running database migrations..."
python manage.py migrate --noinput

# Defer background workers briefly so Daphne binds $PORT first on cold starts,
# and use Celery solo pool to stay well within Render free-tier 512 MB RAM.
echo "==> Scheduling background phase scheduler & Celery worker..."
(sleep 2 && exec python manage.py run_scheduler) &
SCHEDULER_PID=$!

(sleep 3 && exec celery -A config worker --loglevel=info --pool=solo --without-gossip --without-mingle --without-heartbeat) &
CELERY_PID=$!

cleanup() {
    echo "==> Shutting down background processes..."
    kill -TERM "$SCHEDULER_PID" "$CELERY_PID" 2>/dev/null || true
}
trap cleanup SIGTERM SIGINT

PORT="${PORT:-8000}"
echo "==> Starting Daphne ASGI server on port $PORT..."
exec daphne -b 0.0.0.0 -p "$PORT" config.asgi:application
