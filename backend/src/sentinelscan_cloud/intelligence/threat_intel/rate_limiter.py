"""Async token-bucket rate limiter."""
from __future__ import annotations
import asyncio, time
class AsyncTokenBucket:
    def __init__(self, rate: float, capacity: int | None = None):
        if rate <= 0: raise ValueError("rate must be positive")
        self.rate = rate
        self.capacity = float(capacity or max(1, int(rate)))
        self.tokens = self.capacity
        self.updated = time.monotonic()
        self._lock = asyncio.Lock()
    async def acquire(self) -> None:
        while True:
            async with self._lock:
                now = time.monotonic()
                self.tokens = min(self.capacity, self.tokens + (now-self.updated)*self.rate)
                self.updated = now
                if self.tokens >= 1:
                    self.tokens -= 1
                    return
                delay = (1-self.tokens)/self.rate
            await asyncio.sleep(delay)
