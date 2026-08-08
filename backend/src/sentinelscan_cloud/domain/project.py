"""Project -- logical grouping of Assets by environment, client, or
business unit (Section 10)."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from sentinelscan_cloud.domain.base import (
    Base,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
)
from sentinelscan_cloud.domain.enums import CriticalityEnum

if TYPE_CHECKING:
    from sentinelscan_cloud.domain.asset import Asset
    from sentinelscan_cloud.domain.organization import Organization
    from sentinelscan_cloud.domain.timeline_event import TimelineEvent


class Project(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "projects"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    # Stage 4 addition (Section 12.3: Prioritization's
    # "Asset criticality (a Project-level setting)" input)
    criticality: Mapped[CriticalityEnum] = mapped_column(
        SAEnum(
            CriticalityEnum,
            name="criticality_enum",
            values_callable=lambda enum: [e.value for e in enum],
        ),
        default=CriticalityEnum.MEDIUM,
        server_default="medium",
        nullable=False,
    )

    organization: Mapped["Organization"] = relationship(
        back_populates="projects"
    )

    assets: Mapped[list["Asset"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )

    timeline_events: Mapped[list["TimelineEvent"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"Project(id={self.id!r}, name={self.name!r})"