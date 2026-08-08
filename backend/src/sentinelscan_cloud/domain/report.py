"""Report -- one normalized, imported scan result (Section 10, Section 11).

A Report is always treated as inert data (Section 4, Section 15):
nothing in this entity or anywhere downstream of it ever executes
anything found inside an imported report.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from sentinelscan_cloud.domain.base import (
    Base,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
)
from sentinelscan_cloud.domain.enums import (
    ReportProcessingStatusEnum,
    SourceEditionEnum,
)

if TYPE_CHECKING:
    from sentinelscan_cloud.domain.api_key import APIKey
    from sentinelscan_cloud.domain.finding import Finding
    from sentinelscan_cloud.domain.report_asset import ReportAsset


class Report(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "reports"

    source_edition: Mapped[SourceEditionEnum] = mapped_column(
        SAEnum(
            SourceEditionEnum,
            name="source_edition_enum",
            values_callable=lambda enum: [e.value for e in enum],
        ),
        nullable=False,
    )

    schema_version: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )

    raw_blob_storage_key: Mapped[str] = mapped_column(
        String(1024),
        nullable=False,
    )

    # IMPORTANT:
    # Database enum uses lowercase values:
    # processing
    # complete
    # failed
    # retrying
    # permanently_failed
    #
    # values_callable forces SQLAlchemy to store enum VALUES,
    # not enum MEMBER names.
    processing_status: Mapped[ReportProcessingStatusEnum] = mapped_column(
        SAEnum(
            ReportProcessingStatusEnum,
            name="report_processing_status_enum",
            values_callable=lambda enum: [e.value for e in enum],
        ),
        default=ReportProcessingStatusEnum.PROCESSING,
        server_default="processing",
        nullable=False,
        index=True,
    )

    processing_failure_reason: Mapped[str | None] = mapped_column(
        String(2048),
        nullable=True,
    )

    retry_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        server_default="0",
        nullable=False,
    )

    next_retry_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    ingested_via_api_key_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey(
            "api_keys.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    ingested_via_api_key: Mapped["APIKey | None"] = relationship(
        back_populates="reports",
    )

    asset_links: Mapped[list["ReportAsset"]] = relationship(
        back_populates="report",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    findings: Mapped[list["Finding"]] = relationship(
        back_populates="report",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return (
            f"Report("
            f"id={self.id!r}, "
            f"source_edition={self.source_edition!r}, "
            f"status={self.processing_status!r}"
            f")"
        )