"""Recommendation -- a prioritized, potentially de-duplicated action item
derived from one or more Findings across one or more Reports
(Section 10, Section 12.3)."""
from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from sentinelscan_cloud.domain.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from sentinelscan_cloud.domain.asset import Asset
    from sentinelscan_cloud.domain.finding import Finding


class Recommendation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "recommendations"

    asset_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("assets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)  # narrative text (Section 12.4)

    # Lower number = higher priority. Produced by the Prioritization
    # module (Section 12.3) from severity, exposure, recurrence, and
    # Asset criticality -- never recomputed at read time (Section 6.2).
    priority_rank: Mapped[int] = mapped_column(Integer, nullable=False)

    asset: Mapped["Asset"] = relationship()
    finding_links: Mapped[list["RecommendationFinding"]] = relationship(
        back_populates="recommendation", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"Recommendation(id={self.id!r}, priority_rank={self.priority_rank!r})"


class RecommendationFinding(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Join entity: a Recommendation can be derived from more than one
    Finding, and (less commonly) a single strong Finding could inform
    more than one Recommendation over time."""

    __tablename__ = "recommendation_findings"

    recommendation_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("recommendations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    finding_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("findings.id", ondelete="CASCADE"), nullable=False, index=True
    )

    recommendation: Mapped["Recommendation"] = relationship(back_populates="finding_links")
    finding: Mapped["Finding"] = relationship(back_populates="recommendation_links")

    def __repr__(self) -> str:  # pragma: no cover
        return f"RecommendationFinding(recommendation_id={self.recommendation_id!r}, finding_id={self.finding_id!r})"
