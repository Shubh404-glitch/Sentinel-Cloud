"""Stage 8 threat-intelligence synchronization orchestration."""
from __future__ import annotations
import logging
from typing import Any
from sentinelscan_cloud.intelligence.threat_intel.providers.registry import ProviderRegistry
log=logging.getLogger(__name__)

class ThreatIntelSyncService:
    def __init__(self, session, organization_id, registry: ProviderRegistry, repositories: dict[str, Any]):
        self.session=session; self.organization_id=organization_id; self.registry=registry; self.repositories=repositories

    async def sync_cve(self,cve_id):
        provider=self.registry.get_with_fallback("nvd")
        records=provider.normalize(await provider.fetch(cve_id))
        if not records:
            provider=self.registry.get("curated"); records=provider.normalize(await provider.fetch(cve_id))
        for record in records:
            data={"id":record.id,"description":record.description,"published":record.published,
                  "modified":record.modified,"source":record.source}
            cve=await self.repositories["cve"].upsert(data)
            for cvss in record.cvss:
                cvss_repo=self.repositories.get("cvss")
                if cvss_repo: await cvss_repo.upsert({"cve_id":record.id,**cvss})
        await self.session.commit()
        return records

    async def sync_epss(self,cve_id):
        p=self.registry.get_with_fallback("epss")
        records=p.normalize(await p.fetch(cve_id))
        for r in records: await self.repositories["epss"].upsert(r.__dict__)
        await self.session.commit(); return records

    async def sync_kev(self,cve_id):
        p=self.registry.get_with_fallback("kev")
        records=[x for x in p.normalize(await p.fetch(cve_id)) if not cve_id or x.cve_id==cve_id]
        for r in records: await self.repositories["kev"].upsert(r.__dict__)
        await self.session.commit(); return records
