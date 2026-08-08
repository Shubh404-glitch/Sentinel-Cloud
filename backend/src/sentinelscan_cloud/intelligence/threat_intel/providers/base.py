"""Structural provider abstraction for Stage 8."""
from __future__ import annotations
from typing import Any, Protocol, TypeVar, Generic
T = TypeVar("T")

class ThreatIntelProvider(Protocol, Generic[T]):
    name: str
    async def fetch(self, query: str | None = None, **kwargs: Any) -> Any: ...
    def normalize(self, raw: Any) -> list[T]: ...

class CuratedThreatIntelProvider:
    name = "curated"
    async def fetch(self, query: str | None = None, **kwargs: Any) -> list[dict[str, Any]]:
        return []
    def normalize(self, raw: Any) -> list[Any]:
        return list(raw or [])
