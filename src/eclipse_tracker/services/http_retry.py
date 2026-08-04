"""Small retry helper for calls to flaky public third-party APIs (rate limits, transient 5xx)."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import httpx


if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable


_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


async def with_retries[T](call: Callable[[], Awaitable[T]], *, attempts: int = 3, base_delay_s: float = 1.0) -> T:
    """Retry `call` with exponential backoff on rate-limit/transient-server-error responses."""
    last_error: httpx.HTTPStatusError | None = None
    for attempt in range(attempts):
        try:
            return await call()
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code not in _RETRYABLE_STATUS_CODES or attempt == attempts - 1:
                raise
            last_error = exc
            await asyncio.sleep(base_delay_s * (2**attempt))
    raise last_error  # pragma: no cover - unreachable, satisfies type checkers
