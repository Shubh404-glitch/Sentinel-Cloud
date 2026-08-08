"""stage 2 -- authentication schema (refresh_tokens)

Revision ID: 0002_stage2_auth_schema
Revises: 0001_initial_schema
Create Date: 2026-07-21 00:00:00

NOTE ON HOW THIS FILE WAS PRODUCED (read before running):
Same sandbox constraint as 0001_initial_schema: no network access, so
`alembic revision --autogenerate` could not be run against a live
database. This migration was hand-authored directly from
src/sentinelscan_cloud/domain/refresh_token.py, in the same
table/column/constraint shape autogenerate would produce. Before
relying on this in a real environment, run
`alembic revision --autogenerate -m "check"` against a database that is
already at revision 0001, with these models importable, and confirm it
detects no further changes -- see the Stage 2 Completion Report for the
exact command.

This migration only adds a table. It does not alter, rename, or drop
anything from 0001_initial_schema -- Stage 1's schema is untouched.
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0002_stage2_auth_schema"
down_revision: Union[str, None] = "0001_initial_schema"
branch_labels: Union[Sequence[str], None] = None
depends_on: Union[Sequence[str], None] = None


def upgrade() -> None:
    # --- refresh_tokens (Section 9: revocable session credential) ---
    op.create_table(
        "refresh_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("hashed_token", sa.String(128), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rotated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_refresh_tokens_user_id", "refresh_tokens", ["user_id"])
    op.create_index("ix_refresh_tokens_hashed_token", "refresh_tokens", ["hashed_token"], unique=True)


def downgrade() -> None:
    op.drop_table("refresh_tokens")
