"""Integration tests for Stage 2 authentication (Section 9).

Requires a reachable PostgreSQL database at DATABASE_URL with migrations
0001 and 0002 applied, and the full dependency stack installed. See
tests/conftest.py and the Stage 2 Completion Report for why these
cannot execute inside this sandbox, and the exact commands to run them
for real.
"""
from __future__ import annotations

from httpx import AsyncClient

from sentinelscan_cloud.domain.enums import RoleEnum
from sentinelscan_cloud.security.api_key_hashing import hash_opaque_token
from sentinelscan_cloud.security.jwt_tokens import decode_access_token


class TestLogin:
    async def test_login_with_correct_credentials_returns_token_pair(self, client: AsyncClient, user_factory):
        user, password = await user_factory(email="alice@example.com", password="s3cure-pw!")

        response = await client.post("/auth/login", json={"email": user.email, "password": password})

        assert response.status_code == 200
        body = response.json()
        assert body["token_type"] == "bearer"
        assert body["expires_in"] > 0
        assert isinstance(body["access_token"], str) and body["access_token"]
        assert isinstance(body["refresh_token"], str) and body["refresh_token"]

        claims = decode_access_token(body["access_token"])
        assert claims.user_id == user.id
        assert claims.organization_id == user.organization_id
        assert claims.role == user.role

    async def test_login_with_wrong_password_returns_401(self, client: AsyncClient, user_factory):
        user, _ = await user_factory(email="bob@example.com", password="the-real-password")

        response = await client.post("/auth/login", json={"email": user.email, "password": "wrong-password"})

        assert response.status_code == 401
        assert "access_token" not in response.json()

    async def test_login_with_unknown_email_returns_401_with_generic_message(self, client: AsyncClient):
        response = await client.post(
            "/auth/login", json={"email": "does-not-exist@example.com", "password": "anything"}
        )

        assert response.status_code == 401
        # Must be the same generic message as a wrong-password failure --
        # never reveal whether the email exists (Section 15).
        assert response.json()["detail"] == "invalid email or password"

    async def test_login_with_inactive_account_returns_401(self, client: AsyncClient, user_factory):
        user, password = await user_factory(email="carol@example.com", password="pw", is_active=False)

        response = await client.post("/auth/login", json={"email": user.email, "password": password})

        assert response.status_code == 401


class TestRefresh:
    async def test_refresh_with_valid_token_returns_new_pair_and_rotates(
        self, client: AsyncClient, user_factory
    ):
        user, password = await user_factory(email="dave@example.com", password="pw")
        login_response = await client.post("/auth/login", json={"email": user.email, "password": password})
        first_pair = login_response.json()

        refresh_response = await client.post("/auth/refresh", json={"refresh_token": first_pair["refresh_token"]})

        assert refresh_response.status_code == 200
        second_pair = refresh_response.json()
        assert second_pair["refresh_token"] != first_pair["refresh_token"]
        assert second_pair["access_token"] != first_pair["access_token"]

    async def test_reusing_a_rotated_refresh_token_is_rejected(self, client: AsyncClient, user_factory):
        user, password = await user_factory(email="erin@example.com", password="pw")
        login_response = await client.post("/auth/login", json={"email": user.email, "password": password})
        first_pair = login_response.json()

        # First use rotates it away.
        first_refresh = await client.post("/auth/refresh", json={"refresh_token": first_pair["refresh_token"]})
        assert first_refresh.status_code == 200

        # Presenting the SAME (already-rotated) token again must be rejected.
        replay_attempt = await client.post("/auth/refresh", json={"refresh_token": first_pair["refresh_token"]})
        assert replay_attempt.status_code == 401

    async def test_reuse_detection_also_revokes_the_token_issued_by_the_replayed_one(
        self, client: AsyncClient, user_factory, db_session
    ):
        """If token A is rotated into token B, and someone replays A,
        token B (which is otherwise still legitimately live) must also
        be revoked -- the whole session family is compromised, not just
        the replayed token (Section 15)."""
        user, password = await user_factory(email="frank@example.com", password="pw")
        login_response = await client.post("/auth/login", json={"email": user.email, "password": password})
        token_a = login_response.json()["refresh_token"]

        first_refresh = await client.post("/auth/refresh", json={"refresh_token": token_a})
        token_b = first_refresh.json()["refresh_token"]

        replay_attempt = await client.post("/auth/refresh", json={"refresh_token": token_a})
        assert replay_attempt.status_code == 401

        # token_b must now also be dead.
        second_refresh_attempt = await client.post("/auth/refresh", json={"refresh_token": token_b})
        assert second_refresh_attempt.status_code == 401

    async def test_refresh_with_unknown_token_returns_401(self, client: AsyncClient):
        response = await client.post("/auth/refresh", json={"refresh_token": "not-a-real-token"})
        assert response.status_code == 401

    async def test_refresh_with_expired_token_returns_401(self, client: AsyncClient, user_factory, db_session):
        import datetime

        from sentinelscan_cloud.domain.refresh_token import RefreshToken
        from sentinelscan_cloud.security.refresh_tokens import generate_refresh_token

        user, _ = await user_factory(email="grace@example.com")
        raw_token = generate_refresh_token()
        expired_record = RefreshToken(
            user_id=user.id,
            hashed_token=hash_opaque_token(raw_token),
            expires_at=datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=1),
        )
        db_session.add(expired_record)
        await db_session.flush()

        response = await client.post("/auth/refresh", json={"refresh_token": raw_token})
        assert response.status_code == 401


class TestLogout:
    async def test_logout_revokes_the_refresh_token(self, client: AsyncClient, user_factory):
        user, password = await user_factory(email="heidi@example.com", password="pw")
        login_response = await client.post("/auth/login", json={"email": user.email, "password": password})
        pair = login_response.json()

        logout_response = await client.post("/auth/logout", json={"refresh_token": pair["refresh_token"]})
        assert logout_response.status_code == 204

        # The now-revoked token must no longer work for a refresh.
        refresh_attempt = await client.post("/auth/refresh", json={"refresh_token": pair["refresh_token"]})
        assert refresh_attempt.status_code == 401

    async def test_logout_is_idempotent(self, client: AsyncClient, user_factory):
        user, password = await user_factory(email="ivan@example.com", password="pw")
        login_response = await client.post("/auth/login", json={"email": user.email, "password": password})
        pair = login_response.json()

        first = await client.post("/auth/logout", json={"refresh_token": pair["refresh_token"]})
        second = await client.post("/auth/logout", json={"refresh_token": pair["refresh_token"]})
        assert first.status_code == 204
        assert second.status_code == 204

    async def test_logout_with_unknown_token_still_returns_204(self, client: AsyncClient):
        response = await client.post("/auth/logout", json={"refresh_token": "never-issued"})
        assert response.status_code == 204


class TestCurrentUser:
    async def test_me_with_valid_token_returns_user(self, client: AsyncClient, user_factory):
        user, password = await user_factory(email="judy@example.com", password="pw", role=RoleEnum.ADMIN)
        login_response = await client.post("/auth/login", json={"email": user.email, "password": password})
        access_token = login_response.json()["access_token"]

        response = await client.get("/auth/me", headers={"Authorization": f"Bearer {access_token}"})

        assert response.status_code == 200
        body = response.json()
        assert body["id"] == str(user.id)
        assert body["organization_id"] == str(user.organization_id)
        assert body["email"] == user.email
        assert body["role"] == RoleEnum.ADMIN.value

    async def test_me_without_token_returns_401(self, client: AsyncClient):
        response = await client.get("/auth/me")
        assert response.status_code == 401

    async def test_me_with_garbage_token_returns_401(self, client: AsyncClient):
        response = await client.get("/auth/me", headers={"Authorization": "Bearer not-a-jwt"})
        assert response.status_code == 401

    async def test_me_with_both_bearer_and_api_key_returns_400(self, client: AsyncClient, user_factory):
        user, password = await user_factory(email="mallory@example.com", password="pw")
        login_response = await client.post("/auth/login", json={"email": user.email, "password": password})
        access_token = login_response.json()["access_token"]

        response = await client.get(
            "/auth/me",
            headers={"Authorization": f"Bearer {access_token}", "X-API-Key": "ssc_live_something"},
        )
        # Rejected by AuthContextMiddleware before it even reaches the route.
        assert response.status_code == 400


class TestTenantIsolationAndRbac:
    async def test_token_from_one_org_cannot_be_used_to_fetch_a_user_scoped_to_another_org(
        self, client: AsyncClient, user_factory, organization, db_session
    ):
        from sentinelscan_cloud.domain.organization import Organization

        other_org = Organization(name="Other Org", slug="other-org-rbac-test")
        db_session.add(other_org)
        await db_session.flush()

        user, password = await user_factory(email="oscar@example.com", password="pw", org=other_org)
        login_response = await client.post("/auth/login", json={"email": user.email, "password": password})
        access_token = login_response.json()["access_token"]

        response = await client.get("/auth/me", headers={"Authorization": f"Bearer {access_token}"})
        assert response.status_code == 200
        assert response.json()["organization_id"] == str(other_org.id)
        # And explicitly NOT the fixture's default organization.
        assert response.json()["organization_id"] != str(organization.id)
