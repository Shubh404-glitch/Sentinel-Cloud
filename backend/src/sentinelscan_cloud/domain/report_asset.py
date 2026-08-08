"""ReportAsset -- join entity: a Report can cover multiple Assets, and an
Asset accumulates many Reports over time (Section 10: Report "belongs to
Asset(s) it covers")."""
from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from sentinelscan_cloud.domain.asset import Asset
from sentinelscan_cloud.domain.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from sentinelscan_cloud.domain.report import Report


class ReportAsset(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "report_assets"
    __table_args__ = (UniqueConstraint("report_id", "asset_id", name="uq_report_asset"),)

    report_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("reports.id", ondelete="CASCADE"), nullable=False, index=True
    )
    asset_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("assets.id", ondelete="CASCADE"), nullable=False, index=True
    )

    report: Mapped["Report"] = relationship(back_populates="asset_links")
    asset: Mapped["Asset"] = relationship(back_populates="report_links")

    def __repr__(self) -> str:  # pragma: no cover
        return f"ReportAsset(report_id={self.report_id!r}, asset_id={self.asset_id!r})"
