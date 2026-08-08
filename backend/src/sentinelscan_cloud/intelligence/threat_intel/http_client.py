"""HTTP transport used by external intelligence providers."""
from __future__ import annotations
from typing import Any
from sentinelscan_cloud.intelligence.threat_intel.cache import TTLCache
from sentinelscan_cloud.intelligence.threat_intel.rate_limiter import AsyncTokenBucket
from sentinelscan_cloud.jobs.retry_policy import RetryPolicy

class HTTPClient:
    def __init__(self, *, timeout: float = 15.0, retries: int = 3, rate: float = 5.0, cache_ttl: float = 300.0):
        self.timeout = timeout
        self.retry_policy = RetryPolicy(max_attempts=retries)
        self.limiter = AsyncTokenBucket(rate)
        self.cache = TTLCache(cache_ttl)

    async def get_json(self, url: str, *, params: dict[str, Any] | None = None, headers: dict[str, str] | None = None,
                       cache_key: str | None = None) -> Any:
        key = cache_key or url + repr(sorted((params or {}).items()))
        cached = self.cache.get(key)
        if cached is not None: return cached
        await self.limiter.acquire()
        import httpx
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(url, params=params, headers=headers)
            response.raise_for_status()
            data = response.json()
        self.cache.set(key, data)
        return data
