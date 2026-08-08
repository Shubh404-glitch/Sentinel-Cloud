"""
Alembic environment script.

Deliberately uses the SYNC database URL (psycopg2 driver) for running
migrations, even though the application itself uses the ASYNC engine
(asyncpg driver, db/session.py) for normal request handling -- Alembic's
migration runner is synchronous, and mixing that with the app's async
engine would be more complex for no benefit. Both URLs point at the same
database (config/settings.py).
"""
from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from sentinelscan_cloud.config.settings import get_settings
from sentinelscan_cloud.domain import Base  # noqa: F401 -- import registers all entities on Base.metadata

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# Override the ini file's (deliberately blank) sqlalchemy.url with the
# real one from application Settings, so migrations always run against
# whatever DATABASE_URL_SYNC the environment defines.
settings = get_settings()
config.set_main_option("sqlalchemy.url", settings.database_url_sync)


def run_migrations_offline() -> None:
    """Generate SQL scripts without a live DB connection (e.g. for
    review before applying to production)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against a real, connected PostgreSQL database."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
