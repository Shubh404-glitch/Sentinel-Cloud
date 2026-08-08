"""
Organization -- the top-level tenant boundary (Section 10).

Every query elsewhere in the system is scoped by Organization at the
repository layer (Section 15: multi-tenant isolation), not just checked
at the API boundary.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from sentinelscan_cloud.domain.base import (
    Base,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
)


if TYPE_CHECKING:
    from sentinelscan_cloud.domain.api_key import APIKey
    from sentinelscan_cloud.domain.audit_log_entry import AuditLogEntry
    from sentinelscan_cloud.domain.project import Project
    from sentinelscan_cloud.domain.user import User


class Organization(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "organizations"


    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )


    slug: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True,
        index=True,
    )


    users: Mapped[list["User"]] = relationship(
        "User",
        back_populates="organization",
        cascade="all, delete-orphan",
    )


    projects: Mapped[list["Project"]] = relationship(
        "Project",
        back_populates="organization",
        cascade="all, delete-orphan",
    )


    api_keys: Mapped[list["APIKey"]] = relationship(
        "APIKey",
        back_populates="organization",
        cascade="all, delete-orphan",
    )


    audit_log_entries: Mapped[list["AuditLogEntry"]] = relationship(
        "AuditLogEntry",
        back_populates="organization",
        cascade="all, delete-orphan",
    )


    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"Organization("
            f"id={self.id!r}, "
            f"slug={self.slug!r}"
            f")"
        )