"""Integration tests for Stage 7's Organization Administration API
(Users, API Keys, Audit Log).

Requires a reachable PostgreSQL database with migrations through 0005
applied, and the full dependency stack installed -- see tests/conftest.py
and the Stage 7 Completion Report for why these cannot execute inside
this sandbox, and the exact commands to run them for real.
"""
from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from sentinelscan_cloud.domain.enums import RoleEnum
from sentinelscan_cloud.domain.organization import Organization
from sentinelscan_cloud.security.jwt_tokens import create_access_token

pytestmark = pytest.mark.anyio


def _bearer_header(*, user_id, organization_id, role: RoleEnum) -> dict:
    token = create_access_token(user_id=user_id, organization_id=organization_id, role=role)
    return {"Authorization": f"Bearer {token}"}


class TestUsersApi:
    async def test_admin_can_list_and_create_users(
        self, client: AsyncClient, organization: Organization, user_factory
    ):
        admin, _ = await user_factory(role=RoleEnum.ADMIN)
        headers = _bearer_header(user_id=admin.id, organization_id=organization.id, role=RoleEnum.ADMIN)

        list_response = await client.get("/users", headers=headers)
        assert list_response.status_code == 200
        assert list_response.json()["total"] >= 1

        create_response = await client.post(
            "/users",
            json={"email": "new.teammate@example.com", "display_name": "New Teammate", "password": "s3cure-pw!", "role": "member"},
            headers=headers,
        )
        assert create_response.status_code == 201
        assert create_response.json()["email"] == "new.teammate@example.com"
        assert "password" not in create_response.json()
        assert "hashed_password" not in create_response.json()

    async def test_member_cannot_create_users(self, client: AsyncClient, organization: Organization, user_factory):
        member, _ = await user_factory(role=RoleEnum.MEMBER)
        headers = _bearer_header(user_id=member.id, organization_id=organization.id, role=RoleEnum.MEMBER)

        response = await client.post(
            "/users",
            json={"email": "nope@example.com", "display_name": "Nope", "password": "pw", "role": "member"},
            headers=headers,
        )
        assert response.status_code == 403

    async def test_member_can_still_list_users(self, client: AsyncClient, organization: Organization, user_factory):
        member, _ = await user_factory(role=RoleEnum.MEMBER)
        headers = _bearer_header(user_id=member.id, organization_id=organization.id, role=RoleEnum.MEMBER)
        response = await client.get("/users", headers=headers)
        assert response.status_code == 200

    async def test_duplicate_email_returns_409(self, client: AsyncClient, organization: Organization, user_factory):
        admin, _ = await user_factory(role=RoleEnum.ADMIN, email="taken@example.com")
        headers = _bearer_header(user_id=admin.id, organization_id=organization.id, role=RoleEnum.ADMIN)

        response = await client.post(
            "/users",
            json={"email": "taken@example.com", "display_name": "Dup", "password": "pw", "role": "member"},
            headers=headers,
        )
        assert response.status_code == 409

    async def test_invalid_role_is_rejected(self, client: AsyncClient, organization: Organization, user_factory):
        admin, _ = await user_factory(role=RoleEnum.ADMIN)
        headers = _bearer_header(user_id=admin.id, organization_id=organization.id, role=RoleEnum.ADMIN)
        response = await client.post(
            "/users",
            json={"email": "x@example.com", "display_name": "X", "password": "pw", "role": "superuser"},
            headers=headers,
        )
        assert response.status_code == 422

    async def test_admin_cannot_demote_or_deactivate_self(
        self, client: AsyncClient, organization: Organization, user_factory
    ):
        admin, _ = await user_factory(role=RoleEnum.ADMIN)
        headers = _bearer_header(user_id=admin.id, organization_id=organization.id, role=RoleEnum.ADMIN)

        demote_response = await client.patch(f"/users/{admin.id}", json={"role": "member"}, headers=headers)
        assert demote_response.status_code == 400

        deactivate_response = await client.patch(f"/users/{admin.id}", json={"is_active": False}, headers=headers)
        assert deactivate_response.status_code == 400

    async def test_admin_can_update_another_users_role(
        self, client: AsyncClient, organization: Organization, user_factory
    ):
        admin, _ = await user_factory(role=RoleEnum.ADMIN)
        member, _ = await user_factory(role=RoleEnum.MEMBER)
        headers = _bearer_header(user_id=admin.id, organization_id=organization.id, role=RoleEnum.ADMIN)

        response = await client.patch(f"/users/{member.id}", json={"role": "admin"}, headers=headers)
        assert response.status_code == 200
        assert response.json()["role"] == "admin"


class TestApiKeysApi:
    async def test_admin_can_create_list_and_revoke_key(
        self, client: AsyncClient, organization: Organization, user_factory
    ):
        admin, _ = await user_factory(role=RoleEnum.ADMIN)
        headers = _bearer_header(user_id=admin.id, organization_id=organization.id, role=RoleEnum.ADMIN)

        create_response = await client.post("/api-keys", json={"name": "Discover ingestion key"}, headers=headers)
        assert create_response.status_code == 201
        body = create_response.json()
        assert body["raw_key"].startswith("ssc_")
        key_id = body["id"]

        list_response = await client.get("/api-keys", headers=headers)
        assert list_response.status_code == 200
        # Never expose the raw key or its hash in the list view.
        for item in list_response.json()["items"]:
            assert "raw_key" not in item
            assert "hashed_key" not in item

        revoke_response = await client.delete(f"/api-keys/{key_id}", headers=headers)
        assert revoke_response.status_code == 204

        list_after_revoke = await client.get("/api-keys", headers=headers)
        revoked_item = next(i for i in list_after_revoke.json()["items"] if i["id"] == key_id)
        assert revoked_item["is_active"] is False
        assert revoked_item["revoked_at"] is not None

    async def test_member_cannot_list_or_create_api_keys(
        self, client: AsyncClient, organization: Organization, user_factory
    ):
        member, _ = await user_factory(role=RoleEnum.MEMBER)
        headers = _bearer_header(user_id=member.id, organization_id=organization.id, role=RoleEnum.MEMBER)

        list_response = await client.get("/api-keys", headers=headers)
        assert list_response.status_code == 403

        create_response = await client.post("/api-keys", json={"name": "nope"}, headers=headers)
        assert create_response.status_code == 403


class TestAuditLogApi:
    async def test_admin_actions_are_recorded_and_listable(
        self, client: AsyncClient, organization: Organization, user_factory
    ):
        admin, _ = await user_factory(role=RoleEnum.ADMIN)
        headers = _bearer_header(user_id=admin.id, organization_id=organization.id, role=RoleEnum.ADMIN)

        await client.post("/api-keys", json={"name": "audit-test-key"}, headers=headers)

        response = await client.get("/audit-log?action=api_key.created", headers=headers)
        assert response.status_code == 200
        assert response.json()["total"] >= 1
        assert all(e["action"] == "api_key.created" for e in response.json()["items"])

    async def test_member_cannot_read_audit_log(self, client: AsyncClient, organization: Organization, user_factory):
        member, _ = await user_factory(role=RoleEnum.MEMBER)
        headers = _bearer_header(user_id=member.id, organization_id=organization.id, role=RoleEnum.MEMBER)
        response = await client.get("/audit-log", headers=headers)
        assert response.status_code == 403


class TestTenantIsolation:
    async def test_admin_of_one_org_cannot_see_another_orgs_users_or_keys(
        self, client: AsyncClient, db_session: AsyncSession, organization: Organization, user_factory
    ):
        other_org = Organization(name="Other Org", slug=f"other-{uuid.uuid4().hex[:8]}")
        db_session.add(other_org)
        await db_session.flush()
        other_admin, _ = await user_factory(role=RoleEnum.ADMIN, org=other_org, email="otheradmin@example.com")
        await db_session.commit()

        my_admin, _ = await user_factory(role=RoleEnum.ADMIN)
        headers = _bearer_header(user_id=my_admin.id, organization_id=organization.id, role=RoleEnum.ADMIN)

        response = await client.get("/users", headers=headers)
        assert response.status_code == 200
        emails = [u["email"] for u in response.json()["items"]]
        assert "otheradmin@example.com" not in emails
