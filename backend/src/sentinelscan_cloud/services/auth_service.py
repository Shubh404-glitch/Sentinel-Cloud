"""AuthService -- the only place login, token issuance, refresh, and
revocation logic lives (Section 9: the API layer is thin and delegates
to the application layer; route handlers in api/routes/auth.py just
validate input shape and shape the response).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from sentinelscan_cloud.config.settings import get_settings
from sentinelscan_cloud.domain.refresh_token import RefreshToken
from sentinelscan_cloud.domain.user import User
from sentinelscan_cloud.repositories.refresh_token_repository import (
    RefreshTokenRepository,
)
from sentinelscan_cloud.repositories.user_repository import UserRepository
from sentinelscan_cloud.security.api_key_hashing import (
    hash_opaque_token,
    verify_opaque_token,
)
from sentinelscan_cloud.security.jwt_tokens import create_access_token
from sentinelscan_cloud.security.password_hashing import verify_password
from sentinelscan_cloud.security.refresh_tokens import (
    generate_refresh_token,
    refresh_token_expiry,
)


class InvalidCredentialsError(Exception):
    """Email/password did not match, or account is inactive.

    Authentication failures intentionally use one generic exception so
    callers cannot determine whether an account exists.
    """


class InvalidRefreshTokenError(Exception):
    """The refresh token is unknown, expired, rotated, or revoked."""


@dataclass(frozen=True)
class TokenPair:
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in_seconds: int = 0


class AuthService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self._refresh_tokens = RefreshTokenRepository(session)

    async def authenticate(
        self,
        *,
        email: str,
        password: str,
    ) -> User:
        """Validate user credentials."""

        user = await UserRepository.get_by_email(
            self.session,
            email,
        )

        if user is None or not user.is_active:
            # Prevent timing-based user enumeration.
            verify_password(
                password,
                _DUMMY_BCRYPT_HASH,
            )

            raise InvalidCredentialsError(
                "invalid email or password"
            )

        if not verify_password(
            password,
            user.hashed_password,
        ):
            raise InvalidCredentialsError(
                "invalid email or password"
            )

        return user

    async def issue_token_pair(
        self,
        user: User,
    ) -> TokenPair:
        """Create access token and refresh token."""

        access_token = create_access_token(
            user_id=user.id,
            organization_id=user.organization_id,
            role=user.role,
        )

        raw_refresh_token = generate_refresh_token()

        refresh_record = RefreshToken(
            user_id=user.id,
            hashed_token=hash_opaque_token(
                raw_refresh_token
            ),
            expires_at=refresh_token_expiry(),
        )

        self._refresh_tokens.add(refresh_record)

        await self.session.flush()

        return TokenPair(
            access_token=access_token,
            refresh_token=raw_refresh_token,
            expires_in_seconds=(
                get_settings().jwt_access_token_expire_minutes * 60
            ),
        )

    async def refresh(
        self,
        raw_refresh_token: str,
    ) -> TokenPair:
        """Rotate refresh token.

        A refresh token can only be used once.
        Reuse detection revokes the complete token family.
        """

        hashed = hash_opaque_token(
            raw_refresh_token
        )

        record = await self._refresh_tokens.get_by_hashed_token(
            hashed
        )

        if (
            record is None
            or not verify_opaque_token(
                raw_refresh_token,
                record.hashed_token,
            )
        ):
            raise InvalidRefreshTokenError(
                "refresh token not recognized"
            )

        now = datetime.now(timezone.utc)

        #
        # Refresh token replay detection
        #
        if (
            record.revoked_at is not None
            or record.rotated_at is not None
        ):
            await self._refresh_tokens.revoke_all_for_user(
                record.user_id
            )

            # Persist compromise response before returning 401.
            await self.session.commit()

            raise InvalidRefreshTokenError(
                "refresh token has already been used or revoked"
            )

        if record.expires_at <= now:
            raise InvalidRefreshTokenError(
                "refresh token expired"
            )

        user = await UserRepository.get_by_id_unscoped(
            self.session,
            record.user_id,
        )

        if user is None or not user.is_active:
            raise InvalidRefreshTokenError(
                "account inactive"
            )

        # Consume old refresh token.
        await self._refresh_tokens.mark_rotated(
            record
        )

        return await self.issue_token_pair(
            user
        )

    async def revoke_refresh_token(
        self,
        raw_refresh_token: str,
    ) -> None:
        """Logout current session."""

        hashed = hash_opaque_token(
            raw_refresh_token
        )

        record = await self._refresh_tokens.get_by_hashed_token(
            hashed
        )

        if (
            record is not None
            and record.revoked_at is None
        ):
            await self._refresh_tokens.revoke(
                record
            )

            await self.session.flush()


# Used when email does not exist.
# Keeps authentication timing closer to normal password failure.
_DUMMY_BCRYPT_HASH = (
    "$2b$12$CqR6.1DkQmKfE0S9k5C1Xu5j4v0m2W8bqzR6C0z1J5G8w0m4wYb9y"
)