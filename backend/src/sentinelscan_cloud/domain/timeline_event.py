"""TimelineEvent -- a discrete, dated change: new finding, resolved
finding, new/removed asset, score change (Section 10, Section 12.1).
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from sentinelscan_cloud.domain.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from sentinelscan_cloud.domain.enums import TimelineEventTypeEnum


if TYPE_CHECKING:
    from sentinelscan_cloud.domain.asset import Asset
    from sentinelscan_cloud.domain.project import Project


class TimelineEvent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "timeline_events"

    # Belongs to Asset and/or Project (Section 10)
    # Both are nullable because some events are project-level
    # (example: security score changes).
    asset_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("assets.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    project_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    # Use enum values instead of enum names.
    # PostgreSQL stores:
    # finding_new, asset_added, score_changed
    # instead of:
    # FINDING_NEW, ASSET_ADDED, SCORE_CHANGED
    event_type: Mapped[TimelineEventTypeEnum] = mapped_column(
        SAEnum(
            TimelineEventTypeEnum,
            name="timeline_event_type_enum",
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        nullable=False,
    )

    summary: Mapped[str] = mapped_column(
        String(1000),
        nullable=False,
    )

    asset: Mapped["Asset | None"] = relationship(
        back_populates="timeline_events"
    )

    project: Mapped["Project | None"] = relationship(
        back_populates="timeline_events"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"TimelineEvent(id={self.id!r}, "
            f"event_type={self.event_type!r})"
        )