#!/bin/bash
set -e

echo "[auth-service] Running database migrations..."
alembic upgrade head

echo "[auth-service] Starting server..."
exec "$@"
