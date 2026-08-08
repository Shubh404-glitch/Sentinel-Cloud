"""RefreshToken -- a revocable, rotating credential issued alongside a
JWT access token so a session can be extended without re-entering a
password (Section 9: Authentication).

A stateless JWT alone cannot be revoked before it expires. Refresh
tokens close that gap: they are opaque, high-entropy, server-issued
strings tracked in the database, so a session can be individually
revoked (logout, suspected compromise) instead of only expiring.

Only a hash of the token is ever persisted, mirroring ApiKey's
write-only-credential pattern (Section 15) -- the raw token is shown to
the client exactly once, at issuance or rotation, and never again.

`rotated_at` is distinct from `revoked_at` so refresh-token reuse
detection (Section 15: a leaked/stolen token being replayed after it
was already exchanged is a compromise signal) can tell "this token was
legitimately rotated away" apart from "this token was explicitly
revoked" apart from "this token merely expired".
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from sentinelscan_cloud.domain.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class RefreshToken(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "refresh_tokens"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Only the hash is ever persisted (mirrors ApiKey.hashed_key) -- the
    # raw refresh token is returned to the client exactly once.
    hashed_token: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rotated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"RefreshToken(id={self.id!r}, user_id={self.user_id!r}, "
            f"revoked={self.revoked_at is not None!r}, rotated={self.rotated_at is not None!r})"
        )
