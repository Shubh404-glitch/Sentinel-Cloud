"""FIRST EPSS API adapter."""
from __future__ import annotations
from datetime import datetime
from typing import Any
from sentinelscan_cloud.intelligence.threat_intel.http_client import HTTPClient
from sentinelscan_cloud.intelligence.threat_intel.normalization import NormalizedEPSS

class EPSSProvider:
    name="epss"
    base_url="https://api.first.org/data/v1/epss"
    def __init__(self, client: HTTPClient | None=None): self.client=client or HTTPClient()
    async def fetch(self, query: str | None=None, **kwargs: Any):
        params={"cve":query} if query else kwargs
        return await self.client.get_json(self.base_url, params=params)
    def normalize(self, raw: dict) -> list[NormalizedEPSS]:
        out=[]
        for row in raw.get("data", []):
            try: score=float(row["epss"])
            except (KeyError,TypeError,ValueError): continue
            try: pct=float(row["percentile"]) if row.get("percentile") is not None else None
            except (TypeError,ValueError): pct=None
            ts=None
            if row.get("date"):
                try: ts=datetime.fromisoformat(row["date"])
                except ValueError: pass
            out.append(NormalizedEPSS(row.get("cve",""),score,pct,ts))
        return [x for x in out if x.cve_id]
