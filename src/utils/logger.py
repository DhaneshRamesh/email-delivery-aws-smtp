"""Central logging configuration."""
from __future__ import annotations

import logging
from logging.config import dictConfig

from src.core.config import settings


LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {
            "format": "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        }
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "standard",
        }
    },
    "root": {
        "handlers": ["console"],
        "level": "DEBUG" if settings.environment == "development" else "INFO",
    },
}


def configure_logging() -> None:
    """Apply the logging configuration once at application startup."""

    dictConfig(LOGGING_CONFIG)


logger = logging.getLogger("email-delivery")
