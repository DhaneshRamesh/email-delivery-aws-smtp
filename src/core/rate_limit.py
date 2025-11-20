"""Simple in-memory rate limiting helper for demonstration purposes."""
from __future__ import annotations

import asyncio
import time
from typing import Dict, Tuple

from fastapi import HTTPException, status


class RateLimiter:
    """Naive per-tenant rate limiter implemented with an in-memory bucket."""

    def __init__(self, max_per_minute: int) -> None:
        self.max_per_minute = max_per_minute
        self._allowance: Dict[str, Tuple[int, float]] = {}
        self._lock = asyncio.Lock()

    async def check(self, key: str) -> None:
        now = time.monotonic()
        async with self._lock:
            current, last_refill = self._allowance.get(key, (self.max_per_minute, now))
            elapsed = now - last_refill
            refill = int(elapsed / 60 * self.max_per_minute)
            if refill > 0:
                current = min(self.max_per_minute, current + refill)
                last_refill = now
            if current <= 0:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Rate limit exceeded. Please try again shortly.",
                )
            self._allowance[key] = (current - 1, last_refill)


def create_rate_limiter(max_per_minute: int) -> RateLimiter:
    return RateLimiter(max_per_minute=max_per_minute)
