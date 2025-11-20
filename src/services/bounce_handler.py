"""Placeholder bounce/complaint handling service."""
from __future__ import annotations

from typing import Any, Dict

from src.utils.logger import logger


def handle_bounce(payload: Dict[str, Any]) -> None:
    """Process bounce notifications from AWS SNS/SES webhooks."""

    # In production we would persist bounce metadata and mark subscribers inactive.
    logger.warning("Received SES bounce payload: %s", payload)
