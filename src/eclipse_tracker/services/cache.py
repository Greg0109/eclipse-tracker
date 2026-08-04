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

    def get(self, key: str) -> T | None:
        """Return the live cached value for `key`, or None if absent or expired."""
        cached = self._store.get(key)
        if cached is not None and cached[0] > time.monotonic():
            return cached[1]
        return None

    def set(self, key: str, value: T) -> None:
        """Cache `value` under `key` for this cache's TTL."""
        self._store[key] = (time.monotonic() + self._ttl, value)

    async def get_or_set(self, key: str, factory: Callable[[], Awaitable[T]]) -> T:
        """Return the cached value for `key`, or compute and cache it via `factory`."""
        cached = self.get(key)
        if cached is not None:
            return cached

        value = await factory()
        self.set(key, value)
        return value
