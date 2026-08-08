"""SecurityScoreSnapshot -- a point-in-time score for an Asset, Project,
or Organization, produced by the Risk Scoring module per Intelligence
Processing run (Section 10, Section 12.2).

Exactly one of asset_id / project_id / organization_id is populated,
matching `scope`. This is enforced at the application/repository layer
(Section 9) rather than as a schema CHECK constraint here, keeping the
constraint visible in code the same way the rest of the Intelligence
Engine's rules are enforced in code rather than only in the database.
"""
from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Enum as SAEnum
from sqlalchemy import Float, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from sentinelscan_cloud.domain.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from sentinelscan_cloud.domain.enums import SecurityScoreScopeEnum

if TYPE_CHECKING:
    from sentinelscan_cloud.domain.asset import Asset


class SecurityScoreSnapshot(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "security_score_snapshots"

    scope: Mapped[SecurityScoreScopeEnum] = mapped_column(
    SAEnum(
        SecurityScoreScopeEnum,
        name="security_score_scope_enum",
        values_callable=lambda enum_cls: [e.value for e in enum_cls],
    ),
    nullable=False,
) 
    
    asset_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("assets.id", ondelete="CASCADE"), nullable=True, index=True
    )
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=True, index=True
    )
    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True
    )

    score: Mapped[float] = mapped_column(Float, nullable=False)
    # The auditable, rule-based rubric's inputs (Section 12.2: "never an
    # opaque model output the user can't trace back to specific
    # Findings"), shown transparently on the Security Score surface
    # (Section 8).
    contributing_factors: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    asset: Mapped["Asset | None"] = relationship(
        back_populates="score_snapshots", foreign_keys=[asset_id]
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"SecurityScoreSnapshot(id={self.id!r}, scope={self.scope!r}, score={self.score!r})"
