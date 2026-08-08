"""AuditLogEntry -- an immutable record of a security-relevant action
(Section 10, Section 15).

References the acting User/ApiKey and the affected entity. Rows are
append-only at the application layer: nothing in the repository layer
(Section 9) ever updates or deletes an AuditLogEntry.
"""
from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from sentinelscan_cloud.domain.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from sentinelscan_cloud.domain.organization import Organization
    from sentinelscan_cloud.domain.user import User


class AuditLogEntry(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "audit_log_entries"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Nullable because some actions are performed by an ApiKey rather
    # than a User (Section 10: "references the acting User/ApiKey").
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    api_key_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("api_keys.id", ondelete="SET NULL"), nullable=True, index=True
    )

    action: Mapped[str] = mapped_column(String(255), nullable=False)  # e.g. "report.ingested", "api_key.created"
    affected_entity_type: Mapped[str] = mapped_column(String(100), nullable=False)
    affected_entity_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    organization: Mapped["Organization"] = relationship(back_populates="audit_log_entries")
    user: Mapped["User | None"] = relationship(back_populates="audit_log_entries")

    def __repr__(self) -> str:  # pragma: no cover
        return f"AuditLogEntry(id={self.id!r}, action={self.action!r})"
