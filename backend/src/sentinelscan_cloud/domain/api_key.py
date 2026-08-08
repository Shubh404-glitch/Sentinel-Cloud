"""
APIKey -- scoped credential for automated report ingestion.

Only the hash is stored.
Plaintext API keys are shown once during creation.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    String,
)

from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship,
)

from sentinelscan_cloud.domain.base import (
    Base,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
)


if TYPE_CHECKING:
    from sentinelscan_cloud.domain.organization import Organization
    from sentinelscan_cloud.domain.report import Report


class APIKey(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "api_keys"


    organization_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey(
            "organizations.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )


    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )


    hashed_key: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True,
        index=True,
    )


    key_prefix: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
    )


    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )


    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )


    organization: Mapped["Organization"] = relationship(
        "Organization",
        back_populates="api_keys",
    )


    reports: Mapped[list["Report"]] = relationship(
        "Report",
        back_populates="ingested_via_api_key",
    )


    def __repr__(self) -> str:
        return (
            f"APIKey("
            f"id={self.id!r}, "
            f"prefix={self.key_prefix!r}, "
            f"active={self.is_active!r}"
            f")"
        )


# Compatibility for older imports
ApiKey = APIKey