"""
Shared declarative base and mixins for every domain entity in Section 10.

Every entity gets a UUID primary key (appropriate for a multi-tenant
SaaS backend that also has to accept externally-issued identifiers
during ingestion) and created_at/updated_at timestamps, without each
model file having to repeat that boilerplate.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    """The single declarative base for all SentinelScan Cloud domain
    models. Alembic's env.py imports this Base's metadata, so every
    model must ultimately inherit from it to be picked up by
    autogenerate."""


class UUIDPrimaryKeyMixin:
    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )
