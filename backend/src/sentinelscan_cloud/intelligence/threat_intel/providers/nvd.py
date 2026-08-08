"""NVD JSON 2.0 adapter."""
from __future__ import annotations
from datetime import datetime
from typing import Any
from sentinelscan_cloud.intelligence.threat_intel.http_client import HTTPClient
from sentinelscan_cloud.intelligence.threat_intel.normalization import NormalizedCVE

class NVDProvider:
    name = "nvd"
    base_url = "https://services.nvd.nist.gov/rest/json/cves/2.0"
    def __init__(self, client: HTTPClient | None = None):
        self.client = client or HTTPClient()
    async def fetch(self, query: str | None = None, **kwargs: Any) -> dict:
        params = {"cveId": query} if query else kwargs
        return await self.client.get_json(self.base_url, params=params)
    def normalize(self, raw: dict) -> list[NormalizedCVE]:
        out=[]
        for item in raw.get("vulnerabilities", []):
            cve=item.get("cve", {})
            cid=cve.get("id")
            if not cid: continue
            desc=next((d.get("value") for d in cve.get("descriptions", []) if d.get("lang")=="en"), None)
            metrics=cve.get("metrics", {})
            cvss=[]
            for key in ("cvssMetricV31","cvssMetricV30","cvssMetricV2"):
                for m in metrics.get(key, []):
                    d=m.get("cvssData", {})
                    cvss.append({"version": d.get("version"), "base_score": d.get("baseScore"),
                                 "vector": d.get("vectorString"), "severity": d.get("baseSeverity")})
            def dt(x):
                try: return datetime.fromisoformat(x.replace("Z","+00:00")) if x else None
                except ValueError: return None
            out.append(NormalizedCVE(cid, desc, dt(cve.get("published")), dt(cve.get("lastModified")), "nvd", cvss))
        return out
