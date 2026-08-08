"""Always-available curated provider."""
from __future__ import annotations
from sentinelscan_cloud.intelligence.threat_intel.normalization import NormalizedCVE
class CuratedProvider:
    name="curated"
    async def fetch(self, query=None, **kwargs):
        return [{"id":query,"description":"Curated SentinelScan vulnerability reference","source":"curated"}] if query else []
    def normalize(self, raw):
        return [NormalizedCVE(x["id"],x.get("description"),source="curated") for x in (raw or []) if x.get("id")]
