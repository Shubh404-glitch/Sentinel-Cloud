"""CISA Known Exploited Vulnerabilities catalog adapter."""
from __future__ import annotations
from datetime import datetime
from sentinelscan_cloud.intelligence.threat_intel.http_client import HTTPClient
from sentinelscan_cloud.intelligence.threat_intel.normalization import NormalizedKEV
class KEVProvider:
    name="kev"; base_url="https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json"
    def __init__(self, client=None): self.client=client or HTTPClient()
    async def fetch(self, query=None, **kwargs): return await self.client.get_json(self.base_url)
    def normalize(self, raw):
        out=[]
        for x in raw.get("vulnerabilities",[]):
            cve=x.get("cveID")
            if not cve: continue
            def d(k):
                try: return datetime.fromisoformat(x[k]) if x.get(k) else None
                except ValueError: return None
            out.append(NormalizedKEV(cve,x.get("vendorProject"),x.get("product"),d("dateAdded"),d("dueDate"),
                                     str(x.get("knownRansomwareCampaignUse","")).lower()=="known",
                                     x.get("requiredAction")))
        return out
