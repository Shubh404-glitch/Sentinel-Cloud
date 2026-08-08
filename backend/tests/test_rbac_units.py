"""Unit tests for the require_role RBAC dependency (Section 15). Uses
plain in-memory User instances (not persisted) since require_role's
logic operates purely on a User object it's handed -- no DB or HTTP
needed to exercise it.

Still requires fastapi installed (for HTTPException/status), which this
sandbox does not have -- see the Stage 2 Completion Report.
"""
from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException

from sentinelscan_cloud.api.deps.auth import require_role
from sentinelscan_cloud.domain.enums import RoleEnum
from sentinelscan_cloud.domain.user import User


def _make_user(role: RoleEnum) -> User:
    return User(
        id=uuid.uuid4(),
        organization_id=uuid.uuid4(),
        email="rbac-test@example.com",
        hashed_password="irrelevant-for-this-test",
        display_name="RBAC Test User",
        role=role,
        is_active=True,
    )


class TestRequireRole:
    async def test_allows_user_with_permitted_role(self):
        dependency = require_role(RoleEnum.ADMIN)
        admin = _make_user(RoleEnum.ADMIN)

        result = await dependency(user=admin)

        assert result is admin

    async def test_rejects_user_without_permitted_role(self):
        dependency = require_role(RoleEnum.ADMIN)
        member = _make_user(RoleEnum.MEMBER)

        with pytest.raises(HTTPException) as exc_info:
            await dependency(user=member)

        assert exc_info.value.status_code == 403

    async def test_allows_any_of_multiple_permitted_roles(self):
        dependency = require_role(RoleEnum.ADMIN, RoleEnum.MEMBER)
        member = _make_user(RoleEnum.MEMBER)

        result = await dependency(user=member)

        assert result is member

    def test_require_role_with_no_roles_raises_at_definition_time(self):
        # A route accidentally written as Depends(require_role()) with no
        # arguments would silently forbid everyone -- fail fast instead,
        # at import/definition time, not at request time.
        with pytest.raises(ValueError):
            require_role()
