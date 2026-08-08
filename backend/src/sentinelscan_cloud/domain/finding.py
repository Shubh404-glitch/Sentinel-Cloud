"""
Finding -- one normalized security observation from a Report
(Section 10).
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from sentinelscan_cloud.domain.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from sentinelscan_cloud.domain.enums import SeverityEnum


if TYPE_CHECKING:
    from sentinelscan_cloud.domain.asset import Asset
    from sentinelscan_cloud.domain.recommendation import RecommendationFinding
    from sentinelscan_cloud.domain.report import Report
    from sentinelscan_cloud.domain.threat_reference_entry import ThreatReferenceEntry


class Finding(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """
    A normalized security finding imported from a SentinelScan report.

    A Finding is always tied to:
    - one Report
    - one Asset

    Raw producer data is stored as inert JSON and never executed.
    """

    __tablename__ = "findings"

    report_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("reports.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    asset_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("assets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    threat_reference_entry_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("threat_reference_entries.id", ondelete="SET NULL"),
        nullable=True,
    )

    title: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )

    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    # IMPORTANT:
    # PostgreSQL enum values are:
    # low, medium, high, critical
    #
    # SQLAlchemy normally stores enum names:
    # LOW, MEDIUM, HIGH, CRITICAL
    #
    # values_callable forces SQLAlchemy to store:
    # LOW -> "low"
    # HIGH -> "high"
    #
    severity: Mapped[SeverityEnum] = mapped_column(
        SAEnum(
            SeverityEnum,
            name="severity_enum",
            values_callable=lambda enum_cls: [
                member.value for member in enum_cls
            ],
        ),
        nullable=False,
    )

    source_recommendation_text: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Correlation state.
    # Filled later by Intelligence Processing.
    is_new: Mapped[bool | None] = mapped_column(
        nullable=True
    )

    is_resolved: Mapped[bool | None] = mapped_column(
        nullable=True
    )

    is_recurring: Mapped[bool | None] = mapped_column(
        nullable=True
    )

    # Imported producer data.
    # Stored as JSONB and treated as inert data.
    cve_ids: Mapped[list | None] = mapped_column(
        JSONB,
        nullable=True,
    )

    signature: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
    )

    evidence: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
    )

    # Stable fingerprint used for future correlation.
    correlation_fingerprint: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )

    report: Mapped["Report"] = relationship(
        back_populates="findings"
    )

    asset: Mapped["Asset"] = relationship(
        back_populates="findings"
    )

    threat_reference_entry: Mapped["ThreatReferenceEntry | None"] = relationship(
        back_populates="matched_findings"
    )

    recommendation_links: Mapped[list["RecommendationFinding"]] = relationship(
        back_populates="finding",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return (
            f"Finding(id={self.id!r}, "
            f"severity={self.severity!r}, "
            f"title={self.title!r})"
        )