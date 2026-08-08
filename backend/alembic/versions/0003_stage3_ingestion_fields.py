"""stage3 ingestion fields -- assets.tags/extensions, findings.cve_ids/signature/evidence/correlation_fingerprint

Revision ID: 0003_stage3_ingestion_fields
Revises: 0002_stage2_auth_schema
Create Date: 2026-07-21 00:00:00

Purely additive: every new column is nullable (or, for
correlation_fingerprint, backfilled before being required -- see the
data migration note below) so this never breaks existing rows. No table
is created, dropped, or renamed.

Why this migration exists: the approved Report Export Schema v1
(schemas/report_export/v1/) requires producers to send assets[].tags,
assets[].extensions, findings[].cve_ids, findings[].signature, and
findings[].evidence, and Stage 3's Correlation preparation (Section
12.1) requires a stable, Cloud-computed fingerprint per Finding -- none
of which had a column in Stage 1/2's domain model. This was flagged,
not silently added -- see the Stage 3 Completion Report.

NOTE ON EXECUTION (same sandbox limitation as 0001/0002): this could not
actually be run against a live database in this environment -- see the
Stage 3 Completion Report for the exact command to run it for real.
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003_stage3_ingestion_fields"
down_revision: Union[str, None] = "0002_stage2_auth_schema"
branch_labels: Union[Sequence[str], None] = None
depends_on: Union[Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("assets", sa.Column("tags", postgresql.JSONB(), nullable=True))
    op.add_column("assets", sa.Column("extensions", postgresql.JSONB(), nullable=True))

    op.add_column("findings", sa.Column("cve_ids", postgresql.JSONB(), nullable=True))
    op.add_column("findings", sa.Column("signature", postgresql.JSONB(), nullable=True))
    op.add_column("findings", sa.Column("evidence", postgresql.JSONB(), nullable=True))

    # correlation_fingerprint is declared NOT NULL on the model (every
    # Finding ingested from Stage 3 onward always gets one computed at
    # normalization time), but existing rows from before this migration
    # have none. Add nullable, backfill with a placeholder so the
    # column can exist on old rows without crashing existing data, then
    # tighten to NOT NULL. In a real deployment with actual pre-Stage-3
    # Finding rows, replace the placeholder backfill with a real
    # backfill script that computes the true fingerprint per existing
    # row instead.
    op.add_column("findings", sa.Column("correlation_fingerprint", sa.String(64), nullable=True))
    op.execute(
        "UPDATE findings SET correlation_fingerprint = md5(id::text) WHERE correlation_fingerprint IS NULL"
    )
    op.alter_column("findings", "correlation_fingerprint", nullable=False)
    op.create_index("ix_findings_correlation_fingerprint", "findings", ["correlation_fingerprint"])


def downgrade() -> None:
    op.drop_index("ix_findings_correlation_fingerprint", table_name="findings")
    op.drop_column("findings", "correlation_fingerprint")
    op.drop_column("findings", "evidence")
    op.drop_column("findings", "signature")
    op.drop_column("findings", "cve_ids")
    op.drop_column("assets", "extensions")
    op.drop_column("assets", "tags")
