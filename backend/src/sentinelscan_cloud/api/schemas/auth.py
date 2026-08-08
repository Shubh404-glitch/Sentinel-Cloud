"""Request/response shapes for api/routes/auth.py.

`email` is typed as plain `str`, not pydantic's `EmailStr` -- EmailStr
requires the `email-validator` package, which is not in Stage 1's
requirements.txt/pyproject.toml. Adding a new third-party dependency for
Stage 2 wasn't part of the approved scope, so format validation is left
to "does this email exist and does the password match" at the
authentication layer, which is the check that actually matters for a
login endpoint.
"""
from __future__ import annotations

import uuid

from pydantic import BaseModel, Field

from sentinelscan_cloud.domain.enums import RoleEnum


class LoginRequest(BaseModel):
    email: str = Field(min_length=1, max_length=320)
    password: str = Field(min_length=1, max_length=72)


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=1)


class LogoutRequest(BaseModel):
    refresh_token: str = Field(min_length=1)


class TokenPairResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class CurrentUserResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    email: str
    display_name: str
    role: RoleEnum
    is_active: bool
