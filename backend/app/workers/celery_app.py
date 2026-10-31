import logging
import socket

from backend.app.core.config import settings
from celery import Celery

logger = logging.getLogger(__name__)


def is_redis_available(host: str = "localhost", port: int = 6379, timeout: float = 0.5) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except Exception:
        return False


redis_online = is_redis_available(settings.REDIS_HOST, settings.REDIS_PORT)

celery_app = Celery(
    "doc_intel_worker",
    broker=settings.CELERY_BROKER_URL if redis_online else "memory://",
    backend=settings.CELERY_RESULT_BACKEND if redis_online else None,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_always_eager=not redis_online,
    task_eager_propagates=True,
    task_ignore_result=not redis_online,
    broker_connection_retry=False,
    broker_connection_retry_on_startup=False,
    broker_connection_max_retries=1,
)

if not redis_online:
    logger.info(
        "Redis is offline. Celery configured in eager/in-memory mode for standalone operation."
    )


def has_active_worker(timeout: float = 0.5) -> bool:
    """Return True only when a live Celery worker answers a control ping."""
    if not redis_online:
        return False
    try:
        responses = celery_app.control.inspect(timeout=timeout).ping()
        return bool(responses)
    except Exception as exc:
        logger.info("Celery worker health check unavailable: %s", exc)
        return False
