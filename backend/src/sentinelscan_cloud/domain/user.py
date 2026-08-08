"""User -- a person with access to an Organization (Section 10)."""
from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Enum as SAEnum, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from sentinelscan_cloud.domain.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from sentinelscan_cloud.domain.enums import RoleEnum

if TYPE_CHECKING:
    from sentinelscan_cloud.domain.audit_log_entry import AuditLogEntry
    from sentinelscan_cloud.domain.organization import Organization


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "users"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    email: Mapped[str] = mapped_column(
        String(320),
        nullable=False,
        unique=True,
        index=True,
    )

    hashed_password: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    display_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    role: Mapped[RoleEnum] = mapped_column(
        SAEnum(
            RoleEnum,
            name="role_enum",
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        default=RoleEnum.MEMBER,
        nullable=False,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    organization: Mapped["Organization"] = relationship(back_populates="users")
    audit_log_entries: Mapped[list["AuditLogEntry"]] = relationship(back_populates="user")

    def __repr__(self) -> str:  # pragma: no cover
        return f"User(id={self.id!r}, email={self.email!r}, role={self.role!r})"