"""Helper for scheduling email jobs using rq-scheduler."""
from __future__ import annotations

import datetime as dt

import redis
from rq_scheduler import Scheduler

from src.core.config import settings
from src.queue.worker import process_email_job
from src.utils.datetime import utcnow

redis_connection = redis.Redis.from_url(settings.redis_url)
scheduler = Scheduler("emails", connection=redis_connection)


def schedule_campaign_send(*, subject: str, recipient: str, body: str, run_at: dt.datetime | None = None):
    """Schedule an email job for future execution."""

    execute_at = run_at or utcnow()
    return scheduler.enqueue_at(
        execute_at,
        process_email_job,
        kwargs={"subject": subject, "recipient": recipient, "body": body},
    )


if __name__ == "__main__":  # pragma: no cover - manual execution
    schedule_campaign_send(
        subject="Scheduler smoke test",
        recipient="developer@example.com",
        body="This job was scheduled via rq-scheduler.",
        run_at=utcnow() + dt.timedelta(minutes=1),
    )
