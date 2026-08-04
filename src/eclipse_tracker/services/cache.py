"""Tiny in-memory async TTL cache used to avoid hammering public third-party APIs."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable


class TTLCache[T]:
    """Process-local cache with per-entry expiry. Not shared across workers/processes."""

    def __init__(self, ttl_seconds: float) -> None:
        """Create an empty cache with a fixed per-entry TTL in seconds."""
        self._ttl = ttl_seconds
        self._store: dict[str, tuple[float, T]] = {}

    async def get_or_set(self, key: str, factory: Callable[[], Awaitable[T]]) -> T:
        """Return the cached value for `key`, or compute and cache it via `factory`."""
        now = time.monotonic()
        cached = self._store.get(key)
        if cached is not None and cached[0] > now:
            return cached[1]

        value = await factory()
        self._store[key] = (now + self._ttl, value)
        return value
