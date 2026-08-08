"""
Async database engine + session factory for SentinelScan Cloud.

Section 9 (Backend Architecture) requires the API layer to stay thin and
delegate to the application/repository layers; this module is the one
place a SQLAlchemy engine and session factory are constructed, so every
other layer depends on this instead of configuring its own connection.
"""
from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from sentinelscan_cloud.config.settings import get_settings

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_async_engine(
            settings.database_url,
            echo=settings.debug,
            pool_pre_ping=True,
        )
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            bind=get_engine(),
            expire_on_commit=False,
            class_=AsyncSession,
        )
    return _session_factory


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency: yields a request-scoped AsyncSession and
    guarantees it is closed afterwards, regardless of success or
    exception -- one failing request must never leak a connection."""
    session_factory = get_session_factory()
    async with session_factory() as session:
        yield session


async def check_database_connectivity() -> bool:
    """Used by the health-check endpoint (Section 9). Runs the cheapest
    possible round-trip query against PostgreSQL to prove the connection
    pool can actually reach the database, not just that the engine object
    was constructed."""
    from sqlalchemy import text

    engine = get_engine()
    async with engine.connect() as conn:
        result = await conn.execute(text("SELECT 1"))
        return result.scalar_one() == 1
