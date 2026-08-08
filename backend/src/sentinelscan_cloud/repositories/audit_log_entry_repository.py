"""Repository for AuditLogEntry. Append-only by design (Section 15):
this repository deliberately exposes no update/delete method -- see
domain/audit_log_entry.py's module docstring."""
from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from sentinelscan_cloud.domain.audit_log_entry import AuditLogEntry
from sentinelscan_cloud.repositories.base import OrganizationScopedRepository


class AuditLogEntryRepository(OrganizationScopedRepository[AuditLogEntry]):
    model = AuditLogEntry
    organization_scope_column = AuditLogEntry.organization_id

    def record(
        self,
        *,
        action: str,
        affected_entity_type: str,
        affected_entity_id: uuid.UUID | None,
        user_id: uuid.UUID | None = None,
        api_key_id: uuid.UUID | None = None,
        metadata: dict | None = None,
    ) -> AuditLogEntry:
        entry = AuditLogEntry(
            organization_id=self.organization_id,
            user_id=user_id,
            api_key_id=api_key_id,
            action=action,
            affected_entity_type=affected_entity_type,
            affected_entity_id=affected_entity_id,
            metadata_json=metadata or {},
        )
        self.session.add(entry)
        return entry

    async def list_filtered(
        self,
        *,
        action: str | None = None,
        affected_entity_type: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[AuditLogEntry]:
        """Stage 7 addition (Audit Log read API): the base class's
        list_all has no filter parameters. Newest first -- an audit log
        reader wants the most recent activity, unlike most other
        listings in this codebase which don't have an inherent
        chronological-relevance direction."""
        stmt = select(AuditLogEntry).where(AuditLogEntry.organization_id == self.organization_id)
        if action:
            stmt = stmt.where(AuditLogEntry.action == action)
        if affected_entity_type:
            stmt = stmt.where(AuditLogEntry.affected_entity_type == affected_entity_type)
        stmt = stmt.order_by(AuditLogEntry.created_at.desc()).limit(limit).offset(offset)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count_filtered(
        self, *, action: str | None = None, affected_entity_type: str | None = None
    ) -> int:
        stmt = select(func.count(AuditLogEntry.id)).where(AuditLogEntry.organization_id == self.organization_id)
        if action:
            stmt = stmt.where(AuditLogEntry.action == action)
        if affected_entity_type:
            stmt = stmt.where(AuditLogEntry.affected_entity_type == affected_entity_type)
        return (await self.session.execute(stmt)).scalar_one()
