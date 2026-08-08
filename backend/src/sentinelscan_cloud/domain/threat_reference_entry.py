"""ThreatReferenceEntry -- a curated knowledge-base record used for
correlation (Section 10, Section 12.5).

This is SentinelScan Cloud's own maintained reference data, populated
and updated independently of any ingested Report -- never a live
external feed in v1 (Section 13, Section 17)."""
from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from sentinelscan_cloud.domain.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from sentinelscan_cloud.domain.finding import Finding


class ThreatReferenceEntry(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "threat_reference_entries"

    # The signature this entry matches against: service + version +
    # configuration pattern (Section 12.5).
    signature: Mapped[str] = mapped_column(String(500), nullable=False, unique=True, index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    known_risk_context: Mapped[str] = mapped_column(Text, nullable=False)

    matched_findings: Mapped[list["Finding"]] = relationship(back_populates="threat_reference_entry")

    def __repr__(self) -> str:  # pragma: no cover
        return f"ThreatReferenceEntry(id={self.id!r}, signature={self.signature!r})"
