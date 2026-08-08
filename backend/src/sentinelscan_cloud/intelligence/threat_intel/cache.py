"""Small async-safe in-memory TTL cache."""
from __future__ import annotations
import time
from dataclasses import dataclass
from typing import Any
@dataclass
class _Entry:
    value: Any
    expires_at: float
class TTLCache:
    def __init__(self, ttl_seconds: float = 300):
        self.ttl_seconds = ttl_seconds
        self._data: dict[str, _Entry] = {}
    def get(self, key: str) -> Any | None:
        e = self._data.get(key)
        if e is None or e.expires_at <= time.monotonic():
            self._data.pop(key, None); return None
        return e.value
    def set(self, key: str, value: Any) -> None:
        self._data[key] = _Entry(value, time.monotonic()+self.ttl_seconds)
    def clear(self) -> None:
        self._data.clear()
