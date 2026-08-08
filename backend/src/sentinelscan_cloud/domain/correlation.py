"""Stage 8 correlation and attack-chain entities."""
from __future__ import annotations
import uuid
from sqlalchemy import Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column
from sentinelscan_cloud.domain.base import Base, TimestampMixin

class CorrelationResult(Base, TimestampMixin):
    __tablename__ = "correlation_results"
    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    finding_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("findings.id", ondelete="CASCADE"), index=True)
    intel_type: Mapped[str] = mapped_column(String(60))
    intel_id: Mapped[str] = mapped_column(String(300))
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    relationship_type: Mapped[str] = mapped_column(String(100), default="matches")
    evidence: Mapped[dict | None] = mapped_column(JSONB)
    __table_args__ = (UniqueConstraint("organization_id", "finding_id", "intel_type", "intel_id", name="uq_correlation_org_finding_intel"),)

class RelatedFindingGroup(Base, TimestampMixin):
    __tablename__ = "related_finding_groups"
    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    label: Mapped[str | None] = mapped_column(String(300))

class RelatedFindingGroupMember(Base):
    __tablename__ = "related_finding_group_members"
    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    group_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("related_finding_groups.id", ondelete="CASCADE"), index=True)
    finding_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("findings.id", ondelete="CASCADE"), index=True)
    relationship_type: Mapped[str] = mapped_column(String(100), default="related")
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    evidence: Mapped[dict | None] = mapped_column(JSONB)
    __table_args__ = (UniqueConstraint("group_id", "finding_id", name="uq_related_group_finding"),)

class AttackChain(Base, TimestampMixin):
    __tablename__ = "attack_chains"
    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    name: Mapped[str | None] = mapped_column(String(300))
    graph: Mapped[dict] = mapped_column(JSONB, default=dict)
