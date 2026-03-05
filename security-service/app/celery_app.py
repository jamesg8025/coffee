"""
Celery application configuration for the security-service.

The worker runs alongside (but separate from) the FastAPI app.
It uses Redis as both the message broker and the result backend.

Celery Beat schedule:
  - dependency_scan: runs every day at 02:00 UTC in production.
    In dev, the interval is set to 1 hour so you can observe it.

To start the worker + beat scheduler locally:
    docker compose exec security-worker celery -A app.celery_app worker \
        --loglevel=info -B

Interview talking point:
  "Celery Beat is the scheduler that enqueues tasks on a crontab.
  The worker process picks them up from the Redis queue and executes them.
  Results land in security_scan_log so the FastAPI app can serve them."
"""

import os

from celery import Celery
from celery.schedules import crontab

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "security",
    broker=REDIS_URL,
    backend=REDIS_URL.replace("/0", "/1"),  # separate DB for results
    include=["app.tasks.scanner"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    # Beat schedule
    beat_schedule={
        "dependency-scan-daily": {
            "task": "app.tasks.scanner.run_dependency_scan",
            # In dev: every hour. In prod you'd use crontab(hour=2, minute=0).
            "schedule": crontab(minute=0),  # top of every hour
        },
    },
)
