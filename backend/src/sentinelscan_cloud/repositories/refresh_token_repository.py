"""Repository for RefreshToken.

Not Organization-scoped: a refresh token is looked up by its hash alone
(the client presents the raw token, not an organization or user id), and
its blast radius is already bounded to a single user_id via the FK --
there is no cross-organization data exposure risk in reading it
directly by hash the way there would be for, say, Asset or Report.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sentinelscan_cloud.domain.refresh_token import RefreshToken
from sentinelscan_cloud.repositories.base import BaseRepository


class RefreshTokenRepository(BaseRepository[RefreshToken]):
    model = RefreshToken

    async def get_by_hashed_token(self, hashed_token: str) -> RefreshToken | None:
        stmt = select(RefreshToken).where(
            RefreshToken.hashed_token == hashed_token
        )

        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def revoke(self, refresh_token: RefreshToken) -> None:
        refresh_token.revoked_at = datetime.now(timezone.utc)

    async def mark_rotated(self, refresh_token: RefreshToken) -> None:
        refresh_token.rotated_at = datetime.now(timezone.utc)

    async def revoke_all_for_user(self, user_id) -> None:
        """
        Revoke every active refresh token belonging to the user.

        Used when refresh-token reuse is detected. This invalidates the
        entire token family because reuse indicates possible credential
        theft.
        """

        now = datetime.now(timezone.utc)

        stmt = select(RefreshToken).where(
            RefreshToken.user_id == user_id,
            RefreshToken.revoked_at.is_(None),
        )

        result = await self.session.execute(stmt)

        for token in result.scalars():
            token.revoked_at = now

        await self.session.flush()