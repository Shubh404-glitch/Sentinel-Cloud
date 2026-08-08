"""Unit tests for security/ primitives -- no database, no HTTP, pure
functions only. Still requires passlib and python-jose installed (see
Stage 2 Completion Report for sandbox limitations).
"""
from __future__ import annotations

import uuid

import pytest

from sentinelscan_cloud.domain.enums import RoleEnum
from sentinelscan_cloud.security.api_key_hashing import (
    generate_api_key,
    hash_opaque_token,
    verify_opaque_token,
)
from sentinelscan_cloud.security.jwt_tokens import (
    InvalidTokenError,
    create_access_token,
    decode_access_token,
)
from sentinelscan_cloud.security.password_hashing import (
    PasswordTooLongError,
    hash_password,
    verify_password,
)
from sentinelscan_cloud.security.refresh_tokens import generate_refresh_token


class TestPasswordHashing:
    def test_hash_then_verify_round_trips(self):
        hashed = hash_password("correct horse battery staple")
        assert verify_password("correct horse battery staple", hashed) is True

    def test_wrong_password_does_not_verify(self):
        hashed = hash_password("correct horse battery staple")
        assert verify_password("wrong password", hashed) is False

    def test_hash_is_not_the_plaintext(self):
        hashed = hash_password("hunter2")
        assert hashed != "hunter2"
        assert "hunter2" not in hashed

    def test_two_hashes_of_the_same_password_differ(self):
        # bcrypt salts each hash independently.
        assert hash_password("same-password") != hash_password("same-password")

    def test_password_over_72_bytes_is_rejected(self):
        with pytest.raises(PasswordTooLongError):
            hash_password("x" * 73)

    def test_verify_against_malformed_hash_returns_false_not_raises(self):
        assert verify_password("anything", "not-a-real-bcrypt-hash") is False


class TestApiKeyAndOpaqueTokenHashing:
    def test_generate_api_key_returns_raw_prefix_and_hash(self):
        raw_key, prefix, hashed = generate_api_key()

        assert raw_key.startswith("ssc_live_")
        assert prefix == raw_key[:12]
        assert hashed == hash_opaque_token(raw_key)

    def test_generated_api_keys_are_unique(self):
        first, _, _ = generate_api_key()
        second, _, _ = generate_api_key()

        assert first != second

    def test_verify_opaque_token_accepts_matching_token(self):
        raw = generate_refresh_token()
        hashed = hash_opaque_token(raw)

        assert verify_opaque_token(raw, hashed) is True

    def test_verify_opaque_token_rejects_wrong_token(self):
        raw = generate_refresh_token()
        hashed = hash_opaque_token(raw)

        assert verify_opaque_token("something-else", hashed) is False

    def test_hash_opaque_token_is_deterministic(self):
        raw = generate_refresh_token()

        assert hash_opaque_token(raw) == hash_opaque_token(raw)


class TestJwtAccessTokens:
    def _claims(self):
        return dict(
            user_id=uuid.uuid4(),
            organization_id=uuid.uuid4(),
            role=RoleEnum.ADMIN,
        )

    def test_create_then_decode_round_trips(self):
        claims_in = self._claims()

        token = create_access_token(**claims_in)
        claims_out = decode_access_token(token)

        assert claims_out.user_id == claims_in["user_id"]
        assert claims_out.organization_id == claims_in["organization_id"]
        assert claims_out.role == claims_in["role"]

    def test_tampered_token_is_rejected(self):
        token = create_access_token(**self._claims())

        # Change payload instead of last Base64URL character.
        # This guarantees signature mismatch.
        parts = token.split(".")
        parts[1] = parts[1][::-1]
        tampered = ".".join(parts)

        with pytest.raises(InvalidTokenError):
            decode_access_token(tampered)

    def test_garbage_string_is_rejected(self):
        with pytest.raises(InvalidTokenError):
            decode_access_token("not-a-jwt-at-all")

    def test_each_token_has_a_unique_jti(self):
        claims = self._claims()

        token_a = create_access_token(**claims)
        token_b = create_access_token(**claims)

        assert decode_access_token(token_a).jti != decode_access_token(token_b).jti