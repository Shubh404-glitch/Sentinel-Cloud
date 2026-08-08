"""Asset -- a host/system SentinelScan Cloud has intelligence on,
aggregated across every Report that ever mentioned it (Section 10)."""
from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from sentinelscan_cloud.domain.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from sentinelscan_cloud.domain.finding import Finding
    from sentinelscan_cloud.domain.project import Project
    from sentinelscan_cloud.domain.report_asset import ReportAsset
    from sentinelscan_cloud.domain.security_score_snapshot import SecurityScoreSnapshot
    from sentinelscan_cloud.domain.timeline_event import TimelineEvent


class Asset(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "assets"

    project_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Identifying label as it appeared in imported reports -- an IP, a
    # hostname, whatever SentinelScan Discover/SentinelScan Operate used
    # as the target identifier for this host.
    identifier: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Stage 3 additions (Report Export Schema v1: assets[].tags,
    # assets[].extensions) -- additive, nullable JSONB, same pattern as
    # SecurityScoreSnapshot.contributing_factors / AuditLogEntry.metadata_json.
    # `extensions` is an open, producer-specific bag (Section 15: passed
    # through, never inspected/executed).
    tags: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    extensions: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Denormalized pointer to the latest SecurityScoreSnapshot for this
    # Asset (Section 10: "one current SecurityScoreSnapshot"), kept
    # alongside the full history in SecurityScoreSnapshot.asset_id so a
    # Dashboard read never has to compute anything at read time
    # (Section 6.2). use_alter=True breaks the circular table-creation
    # dependency between assets <-> security_score_snapshots for Alembic.
    current_security_score_snapshot_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("security_score_snapshots.id", use_alter=True, name="fk_assets_current_score_snapshot"),
        nullable=True,
    )

    project: Mapped["Project"] = relationship(back_populates="assets")
    report_links: Mapped[list["ReportAsset"]] = relationship(back_populates="asset", cascade="all, delete-orphan")
    findings: Mapped[list["Finding"]] = relationship(back_populates="asset", cascade="all, delete-orphan")
    timeline_events: Mapped[list["TimelineEvent"]] = relationship(
        back_populates="asset", cascade="all, delete-orphan"
    )
    score_snapshots: Mapped[list["SecurityScoreSnapshot"]] = relationship(
        back_populates="asset",
        cascade="all, delete-orphan",
        foreign_keys="SecurityScoreSnapshot.asset_id",
    )
    current_security_score_snapshot: Mapped["SecurityScoreSnapshot | None"] = relationship(
        foreign_keys=[current_security_score_snapshot_id],
        viewonly=True,
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"Asset(id={self.id!r}, identifier={self.identifier!r})"
