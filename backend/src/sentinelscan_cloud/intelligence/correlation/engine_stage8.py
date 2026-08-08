"""Stage 8 threat-intelligence correlation engine."""
from __future__ import annotations
from typing import Any
class ThreatIntelCorrelationEngine:
    def __init__(self,repositories:dict[str,Any],organization_id):
        self.repositories=repositories; self.organization_id=organization_id

    async def correlate_finding(self,finding):
        matches=[]
        for cve_id in (finding.cve_ids or []):
            cve=await self.repositories["cve"].get_by_cve_id(cve_id)
            if cve:
                matches.append({"intel_type":"cve","intel_id":cve_id,"confidence":1.0,"relationship_type":"explicit_cve"})
        evidence=finding.evidence or {}
        for key,ioc_type in (("ip","ip"),("domain","domain"),("url","url"),("hash","hash")):
            value=evidence.get(key)
            if value:
                ioc=await self.repositories["ioc"].get_by_value(value,ioc_type)
                if ioc:
                    matches.append({"intel_type":"ioc","intel_id":str(ioc.id),
                                    "confidence":float(ioc.confidence or 0),"relationship_type":"ioc_reputation"})
        return matches
