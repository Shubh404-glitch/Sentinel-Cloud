"""Stage 8 MITRE ATT&CK entities."""
from __future__ import annotations
import uuid
from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column
from sentinelscan_cloud.domain.base import Base, TimestampMixin

class MitreTactic(Base):
    __tablename__ = "mitre_tactics"
    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    name: Mapped[str] = mapped_column(String(300))
    description: Mapped[str | None] = mapped_column(Text)

class MitreTechnique(Base):
    __tablename__ = "mitre_techniques"
    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    name: Mapped[str] = mapped_column(String(300))
    description: Mapped[str | None] = mapped_column(Text)
    tactic_id: Mapped[str | None] = mapped_column(ForeignKey("mitre_tactics.id", ondelete="SET NULL"))

class MitreGroup(Base):
    __tablename__ = "mitre_groups"
    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    name: Mapped[str] = mapped_column(String(300))
    description: Mapped[str | None] = mapped_column(Text)

class MitreTechniqueGroup(Base):
    __tablename__ = "mitre_technique_groups"
    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    technique_id: Mapped[str] = mapped_column(ForeignKey("mitre_techniques.id", ondelete="CASCADE"))
    group_id: Mapped[str] = mapped_column(ForeignKey("mitre_groups.id", ondelete="CASCADE"))
    __table_args__ = (UniqueConstraint("technique_id", "group_id", name="uq_mitre_technique_group"),)
