"""Stage 8 vulnerability intelligence domain entities."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from sentinelscan_cloud.domain.base import Base, TimestampMixin


class CVE(Base, TimestampMixin):
    __tablename__ = "cves"

    id: Mapped[str] = mapped_column(
        String(32),
        primary_key=True,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
    )

    published: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
    )

    modified: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
    )

    source: Mapped[str] = mapped_column(
        String(100),
        default="curated",
        nullable=False,
    )

    cvss: Mapped[list["CVSS"]] = relationship(
        cascade="all, delete-orphan",
        back_populates="cve",
    )

    epss: Mapped[list["EPSS"]] = relationship(
        cascade="all, delete-orphan",
        back_populates="cve",
    )

    kev_entries: Mapped[list["KEV"]] = relationship(
        cascade="all, delete-orphan",
        back_populates="cve",
    )


class CVSS(Base):
    __tablename__ = "cvss"

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    cve_id: Mapped[str] = mapped_column(
        ForeignKey(
            "cves.id",
            ondelete="CASCADE",
        ),
        index=True,
    )

    version: Mapped[str] = mapped_column(
        String(20),
    )

    base_score: Mapped[float | None] = mapped_column(
        Float,
    )

    vector: Mapped[str | None] = mapped_column(
        String(300),
    )

    severity: Mapped[str | None] = mapped_column(
        String(30),
    )

    cve: Mapped[CVE] = relationship(
        back_populates="cvss",
    )


class CWE(Base):
    __tablename__ = "cwes"

    id: Mapped[str] = mapped_column(
        String(32),
        primary_key=True,
    )

    name: Mapped[str] = mapped_column(
        String(300),
    )

    description: Mapped[str | None] = mapped_column(
        Text,
    )


class EPSS(Base):
    __tablename__ = "epss"

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    cve_id: Mapped[str] = mapped_column(
        ForeignKey(
            "cves.id",
            ondelete="CASCADE",
        ),
        index=True,
    )

    score: Mapped[float] = mapped_column(
        Float,
    )

    percentile: Mapped[float | None] = mapped_column(
        Float,
    )

    timestamp: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
    )

    cve: Mapped[CVE] = relationship(
        back_populates="epss",
    )

    __table_args__ = (
        UniqueConstraint(
            "cve_id",
            "timestamp",
            name="uq_epss_cve_timestamp",
        ),
    )


class KEV(Base):
    __tablename__ = "kevs"

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    cve_id: Mapped[str] = mapped_column(
        ForeignKey(
            "cves.id",
            ondelete="CASCADE",
        ),
        index=True,
    )

    vendor: Mapped[str | None] = mapped_column(
        String(300),
    )

    product: Mapped[str | None] = mapped_column(
        String(500),
    )

    date_added: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
    )

    due_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
    )

    ransomware_use: Mapped[bool | None] = mapped_column(
        Boolean,
    )

    remediation: Mapped[str | None] = mapped_column(
        Text,
    )

    cve: Mapped[CVE] = relationship(
        back_populates="kev_entries",
    )


class VendorAdvisory(Base, TimestampMixin):
    __tablename__ = "vendor_advisories"

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(
            "organizations.id",
            ondelete="CASCADE",
        ),
        index=True,
    )

    advisory_id: Mapped[str] = mapped_column(
        String(300),
    )

    vendor: Mapped[str] = mapped_column(
        String(200),
    )

    title: Mapped[str | None] = mapped_column(
        String(500),
    )

    url: Mapped[str | None] = mapped_column(
        String(2000),
    )

    description: Mapped[str | None] = mapped_column(
        Text,
    )

    published: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
    )

    modified: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
    )

    cve_ids: Mapped[list | None] = mapped_column(
        JSONB,
    )

    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "vendor",
            "advisory_id",
            name="uq_vendor_advisory_org_key",
        ),
    )


class ExploitAvailability(Base):
    __tablename__ = "exploit_availability"

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(
            "organizations.id",
            ondelete="CASCADE",
        ),
        index=True,
    )

    cve_id: Mapped[str] = mapped_column(
        String(32),
        index=True,
    )

    source: Mapped[str] = mapped_column(
        String(200),
    )

    available: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    url: Mapped[str | None] = mapped_column(
        String(2000),
    )

    confidence: Mapped[float | None] = mapped_column(
        Float,
    )

    evidence: Mapped[dict | None] = mapped_column(
        JSONB,
    )

    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "cve_id",
            "source",
            name="uq_exploit_org_cve_source",
        ),
    )