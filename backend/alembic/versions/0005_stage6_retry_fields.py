"""stage6 retry fields -- reports.retry_count, reports.next_retry_at,
report_processing_status_enum + RETRYING/PERMANENTLY_FAILED

Revision ID: 0005_stage6_retry_fields
Revises: 0004_stage4_prioritization_fields
Create Date: 2026-07-26 00:00:00

Purely additive: two new columns (retry_count NOT NULL with a
server_default of 0, matching 0004's pattern; next_retry_at nullable,
since it is meaningless outside the RETRYING state) and two new values
on the existing report_processing_status_enum Postgres type.

Why: Section 9 already described "retried with backoff on transient
failure, but a deterministic failure is marked failed ... not retried
forever", but nothing before Stage 6 implemented that distinction --
see domain/enums.py's ReportProcessingStatusEnum docstring and the
Stage 6 Completion Report.

Postgres note: `ALTER TYPE ... ADD VALUE` cannot be used to add a value
and then reference that same value in the same transaction, but adding
the value itself is transaction-safe as of Postgres 12+ (this project
already targets 12+ via asyncpg/SQLAlchemy 2.0) -- and this migration
does not reference the new values anywhere, only adds them, so there is
no ordering hazard here.

Postgres has no `ALTER TYPE ... DROP VALUE` -- downgrade() therefore
cannot cleanly remove the two new enum values (a real, documented
Postgres limitation, not an oversight here). downgrade() reverses the
column additions only; the enum values are left in place, matching how
this exact limitation is normally handled in production Alembic
migrations.
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005_stage6_retry_fields"
down_revision: Union[str, None] = "0004_stage4_prioritization_fields"
branch_labels: Union[Sequence[str], None] = None
depends_on: Union[Sequence[str], None] = None


def upgrade() -> None:
    # ALTER TYPE ADD VALUE cannot run inside the same statement batch as
    # other DDL in some drivers' autocommit handling -- executed as
    # its own statement, `IF NOT EXISTS` guarding a re-run.
    op.execute("ALTER TYPE report_processing_status_enum ADD VALUE IF NOT EXISTS 'retrying'")
    op.execute("ALTER TYPE report_processing_status_enum ADD VALUE IF NOT EXISTS 'permanently_failed'")

    op.add_column(
        "reports",
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "reports",
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
    )
    # Drop the server_default after backfilling existing rows -- new
    # rows going forward always specify it explicitly via the ORM
    # model's Python-side default, matching 0004's pattern.
    op.alter_column("reports", "retry_count", server_default=None)


def downgrade() -> None:
    op.drop_column("reports", "next_retry_at")
    op.drop_column("reports", "retry_count")
    # See module docstring: the two enum values added in upgrade() are
    # NOT removed here -- Postgres has no ALTER TYPE ... DROP VALUE.
