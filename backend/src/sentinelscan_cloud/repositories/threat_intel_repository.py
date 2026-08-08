"""Tenant-scoped repositories for Stage 8 threat intelligence."""
from __future__ import annotations
import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sentinelscan_cloud.repositories.base import OrganizationScopedRepository
from sentinelscan_cloud.domain.threat_intel_vuln import CVE, CVSS, CWE, EPSS, KEV, VendorAdvisory, ExploitAvailability
from sentinelscan_cloud.domain.threat_intel_ioc import IOC
from sentinelscan_cloud.domain.mitre_attack import MitreTactic, MitreTechnique, MitreGroup, MitreTechniqueGroup
from sentinelscan_cloud.domain.correlation import CorrelationResult, RelatedFindingGroup, RelatedFindingGroupMember, AttackChain

class CVERepository(OrganizationScopedRepository[CVE]):
    model = CVE
    # CVEs are global intelligence; organization_id is enforced by the
    # service boundary for reads/writes that expose tenant-specific data.
    async def get_by_cve_id(self, cve_id: str) -> CVE | None:
        return await self.session.get(CVE, cve_id)
    async def upsert(self, data: dict) -> CVE:
        obj = await self.get_by_cve_id(data["id"])
        if obj is None:
            obj = CVE(id=data["id"])
            self.session.add(obj)
        for k, v in data.items():
            if k != "id" and hasattr(obj, k):
                setattr(obj, k, v)
        return obj

class EPSSRepository(OrganizationScopedRepository[EPSS]):
    model = EPSS
    async def get_for_cve(self, cve_id: str) -> list[EPSS]:
        r = await self.session.execute(select(EPSS).where(EPSS.cve_id == cve_id))
        return list(r.scalars().all())
    async def upsert(self, data: dict) -> EPSS:
        rows = await self.get_for_cve(data["cve_id"])
        timestamp = data.get("timestamp")
        obj = next((x for x in rows if x.timestamp == timestamp), None)
        if obj is None:
            obj = EPSS(cve_id=data["cve_id"])
            self.session.add(obj)
        for k, v in data.items():
            if hasattr(obj, k): setattr(obj, k, v)
        return obj

class KEVRepository(OrganizationScopedRepository[KEV]):
    model = KEV
    async def get_for_cve(self, cve_id: str) -> KEV | None:
        r = await self.session.execute(select(KEV).where(KEV.cve_id == cve_id).limit(1))
        return r.scalar_one_or_none()
    async def upsert(self, data: dict) -> KEV:
        obj = await self.get_for_cve(data["cve_id"])
        if obj is None:
            obj = KEV(cve_id=data["cve_id"]); self.session.add(obj)
        for k,v in data.items():
            if hasattr(obj,k): setattr(obj,k,v)
        return obj

class VendorAdvisoryRepository(OrganizationScopedRepository[VendorAdvisory]):
    model = VendorAdvisory
    organization_scope_column = VendorAdvisory.organization_id
    async def upsert(self, data: dict) -> VendorAdvisory:
        r = await self.session.execute(select(VendorAdvisory).where(
            VendorAdvisory.organization_id == self.organization_id,
            VendorAdvisory.vendor == data["vendor"],
            VendorAdvisory.advisory_id == data["advisory_id"]))
        obj = r.scalar_one_or_none()
        if obj is None:
            obj = VendorAdvisory(organization_id=self.organization_id, advisory_id=data["advisory_id"], vendor=data["vendor"])
            self.session.add(obj)
        for k,v in data.items():
            if hasattr(obj,k) and k not in {"organization_id"}: setattr(obj,k,v)
        return obj

class ExploitAvailabilityRepository(OrganizationScopedRepository[ExploitAvailability]):
    model = ExploitAvailability
    organization_scope_column = ExploitAvailability.organization_id
    async def upsert(self, data: dict) -> ExploitAvailability:
        r = await self.session.execute(select(ExploitAvailability).where(
            ExploitAvailability.organization_id == self.organization_id,
            ExploitAvailability.cve_id == data["cve_id"],
            ExploitAvailability.source == data["source"]))
        obj = r.scalar_one_or_none()
        if obj is None:
            obj = ExploitAvailability(organization_id=self.organization_id, cve_id=data["cve_id"], source=data["source"])
            self.session.add(obj)
        for k,v in data.items():
            if hasattr(obj,k) and k != "organization_id": setattr(obj,k,v)
        return obj

class IOCRepository(OrganizationScopedRepository[IOC]):
    model = IOC
    organization_scope_column = IOC.organization_id
    async def get_by_value(self, value: str, ioc_type: str | None = None) -> IOC | None:
        stmt = select(IOC).where(IOC.organization_id == self.organization_id, IOC.value == value)
        if ioc_type: stmt = stmt.where(IOC.type == ioc_type)
        r = await self.session.execute(stmt.limit(1)); return r.scalar_one_or_none()
    async def upsert(self, data: dict) -> IOC:
        obj = await self.get_by_value(data["value"], data.get("type"))
        if obj is None:
            obj = IOC(organization_id=self.organization_id, value=data["value"], type=data["type"], source=data["source"])
            self.session.add(obj)
        for k,v in data.items():
            if hasattr(obj,k) and k != "organization_id": setattr(obj,k,v)
        return obj

class MitreTacticRepository(OrganizationScopedRepository[MitreTactic]):
    model = MitreTactic
    async def upsert(self, data: dict) -> MitreTactic:
        obj = await self.session.get(MitreTactic, data["id"])
        if obj is None: obj = MitreTactic(id=data["id"]); self.session.add(obj)
        for k,v in data.items():
            if hasattr(obj,k) and k!="id": setattr(obj,k,v)
        return obj

class MitreTechniqueRepository(OrganizationScopedRepository[MitreTechnique]):
    model = MitreTechnique
    async def upsert(self, data: dict) -> MitreTechnique:
        obj = await self.session.get(MitreTechnique, data["id"])
        if obj is None: obj = MitreTechnique(id=data["id"]); self.session.add(obj)
        for k,v in data.items():
            if hasattr(obj,k) and k!="id": setattr(obj,k,v)
        return obj

class MitreGroupRepository(OrganizationScopedRepository[MitreGroup]):
    model = MitreGroup
    async def upsert(self, data: dict) -> MitreGroup:
        obj = await self.session.get(MitreGroup, data["id"])
        if obj is None: obj = MitreGroup(id=data["id"]); self.session.add(obj)
        for k,v in data.items():
            if hasattr(obj,k) and k!="id": setattr(obj,k,v)
        return obj

class CorrelationResultRepository(OrganizationScopedRepository[CorrelationResult]):
    model = CorrelationResult
    organization_scope_column = CorrelationResult.organization_id
    async def upsert(self, data: dict) -> CorrelationResult:
        stmt = select(CorrelationResult).where(
            CorrelationResult.organization_id == self.organization_id,
            CorrelationResult.finding_id == data["finding_id"],
            CorrelationResult.intel_type == data["intel_type"],
            CorrelationResult.intel_id == data["intel_id"])
        r = await self.session.execute(stmt.limit(1)); obj = r.scalar_one_or_none()
        if obj is None:
            obj = CorrelationResult(organization_id=self.organization_id, finding_id=data["finding_id"],
                                    intel_type=data["intel_type"], intel_id=data["intel_id"])
            self.session.add(obj)
        for k,v in data.items():
            if hasattr(obj,k) and k!="organization_id": setattr(obj,k,v)
        return obj

class AttackChainRepository(OrganizationScopedRepository[AttackChain]):
    model = AttackChain
    organization_scope_column = AttackChain.organization_id
    async def add_chain(self, name: str | None, graph: dict) -> AttackChain:
        obj = AttackChain(organization_id=self.organization_id, name=name, graph=graph)
        self.session.add(obj); return obj
