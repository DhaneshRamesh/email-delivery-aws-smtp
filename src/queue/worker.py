"""RQ worker that delivers outbound emails via SES."""
from __future__ import annotations

import os
import sys
from typing import Any

try:  # pragma: no cover - optional dependency import
    import redis  # type: ignore
except ImportError:  # pragma: no cover
    redis = None  # type: ignore

try:  # pragma: no cover
    from rq import Connection, Queue, Worker  # type: ignore
except ImportError:  # pragma: no cover
    Connection = Queue = Worker = None  # type: ignore

from src.core.config import settings
from src.services.ses import SESService
from src.utils.logger import logger

_email_queue: Any | None = None


def _ensure_dependencies() -> None:
    if redis is None or Queue is None or Worker is None:
        raise RuntimeError(
            "redis and rq packages are required for queue processing. Install project dependencies."
        )


def _get_queue() -> Any:
    global _email_queue
    if _email_queue is None:
        _ensure_dependencies()
        connection = redis.Redis.from_url(settings.redis_url)  # type: ignore[union-attr]
        _email_queue = Queue("emails", connection=connection)  # type: ignore[call-arg]
    return _email_queue


def process_email_job(*, subject: str, recipient: str, body: str) -> str:
    """Background job that sends an email."""

    service = SESService()
    message_id = service.send_email(subject=subject, recipient=recipient, text_body=body)
    logger.info("Processed queued email to %s", recipient)
    return message_id


def enqueue_email_job(*, subject: str, recipient: str, body: str):
    """Helper for API routes to enqueue jobs."""

    queue = _get_queue()
    return queue.enqueue(
        process_email_job,
        kwargs={"subject": subject, "recipient": recipient, "body": body},
    )


def run_worker() -> None:
    """Entry point called by `python -m src.queue.worker`."""

    if (
        settings.environment == "development"
        and sys.platform == "darwin"
        and not os.environ.get("OBJC_DISABLE_INITIALIZE_FORK_SAFETY")
    ):
        logger.warning(
            "OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES is recommended on macOS to avoid fork-related crashes with RQ workers. "
            "Applying it for this process."
        )
        os.environ["OBJC_DISABLE_INITIALIZE_FORK_SAFETY"] = "YES"

    queue = _get_queue()
    connection = queue.connection
    with Connection(connection):  # type: ignore[arg-type]
        worker = Worker([queue])
        worker.work(with_scheduler=True)


if __name__ == "__main__":  # pragma: no cover - manual execution
    run_worker()
