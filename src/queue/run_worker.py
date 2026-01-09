"""Run an RQ worker bound to the configured queue."""
from __future__ import annotations

try:  # pragma: no cover - optional dependency import
    import redis  # type: ignore
except ImportError:  # pragma: no cover
    redis = None  # type: ignore

try:  # pragma: no cover
    from rq import Connection, Queue, Worker  # type: ignore
except ImportError:  # pragma: no cover
    Connection = Queue = Worker = None  # type: ignore

from src.core.config import settings


def _ensure_dependencies() -> None:
    if redis is None or Queue is None or Worker is None:
        raise RuntimeError("redis and rq packages are required for queue processing. Install project dependencies.")


def run() -> None:
    """Run an RQ worker on the configured queue."""

    _ensure_dependencies()
    connection = redis.Redis.from_url(settings.redis_url)  # type: ignore[union-attr]
    queue = Queue(settings.rq_queue_name, connection=connection)  # type: ignore[call-arg]
    with Connection(connection):  # type: ignore[arg-type]
        worker = Worker([queue])
        worker.work(with_scheduler=True)


if __name__ == "__main__":  # pragma: no cover - manual execution
    run()
