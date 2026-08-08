"""Shared pytest fixtures for SentinelScan Cloud authentication tests."""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator, Callable

import pytest
import pytest_asyncio

from httpx import ASGITransport, AsyncClient

from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
)

from sentinelscan_cloud.api.main import app
from sentinelscan_cloud.db.session import (
    get_db_session,
    get_engine,
)

from sentinelscan_cloud.domain.enums import RoleEnum
from sentinelscan_cloud.domain.organization import Organization
from sentinelscan_cloud.domain.project import Project
from sentinelscan_cloud.domain.api_key import ApiKey
from sentinelscan_cloud.domain.user import User

from sentinelscan_cloud.security.api_key_hashing import generate_api_key
from sentinelscan_cloud.security.password_hashing import hash_password
from sentinelscan_cloud.api.deps.auth import get_current_api_key

# ---------------------------------------------------------
# Database session fixture
# ---------------------------------------------------------

@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Provides isolated database session per test.

    Strategy:
    - Dedicated connection
    - Outer transaction
    - Nested SAVEPOINT rollback
    - No connection reuse after event loop closes
    """

    engine = get_engine()

    connection = await engine.connect()

    transaction = await connection.begin()

    session_factory = async_sessionmaker(
        bind=connection,
        expire_on_commit=False,
        class_=AsyncSession,
    )

    session = session_factory()

    await connection.begin_nested()

    @event.listens_for(
        session.sync_session,
        "after_transaction_end",
    )
    def restart_savepoint(session_sync, trans):

        if trans.nested and not trans._parent.nested:
            connection.sync_connection.begin_nested()

    try:
        yield session

    finally:

        await session.close()

        if transaction.is_active:
            await transaction.rollback()

        await connection.close()

        # Important:
        # prevents stale asyncpg connections
        # surviving between tests
        await engine.dispose()


# ---------------------------------------------------------
# HTTP Client fixture
# ---------------------------------------------------------

@pytest_asyncio.fixture
async def client(
    db_session: AsyncSession,
) -> AsyncGenerator[AsyncClient, None]:

    async def override_db():
        yield db_session


    app.dependency_overrides[get_db_session] = override_db

    transport = ASGITransport(
        app=app
    )


    async with AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as client:

        yield client


    app.dependency_overrides.clear()



# ---------------------------------------------------------
# Organization fixture
# ---------------------------------------------------------

@pytest_asyncio.fixture
async def organization(
    db_session: AsyncSession,
) -> Organization:


    organization = Organization(
        name="Test Organization",
        slug=f"test-org-{uuid.uuid4().hex[:8]}",
    )

    db_session.add(organization)

    await db_session.flush()

    return organization



# ---------------------------------------------------------
# User factory
# ---------------------------------------------------------

@pytest_asyncio.fixture
async def user_factory(
    db_session: AsyncSession,
    organization: Organization,
) -> Callable:


    async def create_user(
        *,
        email: str | None = None,
        password: str = "correct-horse-battery-staple",
        role: RoleEnum = RoleEnum.MEMBER,
        is_active: bool = True,
        org: Organization | None = None,
    ) -> tuple[User, str]:


        target_org = org or organization


        user = User(
            organization_id=target_org.id,
            email=email
            or f"user-{uuid.uuid4().hex[:8]}@example.com",
            hashed_password=hash_password(password),
            display_name="Test User",
            role=role,
            is_active=is_active,
        )


        db_session.add(user)

        await db_session.flush()


        return user, password


    return create_user



# ---------------------------------------------------------
# Project fixture
# ---------------------------------------------------------

@pytest_asyncio.fixture
async def project(
    db_session: AsyncSession,
    organization: Organization,
) -> Project:


    project = Project(
        organization_id=organization.id,
        name=f"Project-{uuid.uuid4().hex[:8]}",
    )


    db_session.add(project)

    await db_session.flush()


    return project



# ---------------------------------------------------------
# API Key factory
# ---------------------------------------------------------

@pytest_asyncio.fixture
async def api_key_factory(
    db_session: AsyncSession,
    organization: Organization,
):


    async def create_api_key(
        *,
        org: Organization | None = None,
    ) -> tuple[ApiKey, str]:


        target_org = org or organization


        raw_key, prefix, hashed_key = generate_api_key()


        api_key = ApiKey(
            organization_id=target_org.id,
            name=f"Test-Key-{uuid.uuid4().hex[:8]}",
            hashed_key=hashed_key,
            key_prefix=prefix,
            is_active=True,
        )


        db_session.add(api_key)

        await db_session.flush()


        return api_key, raw_key


    return create_api_key



# ---------------------------------------------------------
# Current user
# ---------------------------------------------------------

@pytest_asyncio.fixture
async def current_user(
    user_factory,
) -> User:

    user, _ = await user_factory()

    return user



# ---------------------------------------------------------
# Authentication headers
# ---------------------------------------------------------

@pytest.fixture
def auth_headers(
    current_user: User,
):

    from sentinelscan_cloud.security.jwt_tokens import (
        create_access_token,
    )


    token = create_access_token(
        user_id=current_user.id,
        organization_id=current_user.organization_id,
        role=current_user.role,
    )


    return {
        "Authorization": f"Bearer {token}"
    }



# ---------------------------------------------------------
# Async backend configuration
# ---------------------------------------------------------

@pytest.fixture
def anyio_backend():

    return "asyncio"