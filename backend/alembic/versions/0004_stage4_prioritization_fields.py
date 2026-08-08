"""stage4 prioritization fields -- projects.criticality

Revision ID: 0004_stage4_prioritization_fields
Revises: 0003_stage3_ingestion_fields
Create Date: 2026-07-22 00:00:00

Purely additive: NOT NULL with a server_default so existing rows get a
sane value (medium) without a separate backfill step -- simpler than
0003's nullable-then-backfill-then-tighten approach because there's a
single, defensible default for every existing Project (unlike
correlation_fingerprint in 0003, which has no meaningful universal
default).

Why: Section 12.3 (Prioritization) names "Asset criticality (a
Project-level setting)" as a ranking input, but no column existed for
it anywhere in Stage 1/2/3 -- see domain/enums.py's CriticalityEnum
docstring and the Stage 4 Completion Report.
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004_stage4_prioritization_fields"
down_revision: Union[str, None] = "0003_stage3_ingestion_fields"
branch_labels: Union[Sequence[str], None] = None
depends_on: Union[Sequence[str], None] = None

criticality_enum = sa.Enum("low", "medium", "high", "critical", name="criticality_enum")


def upgrade() -> None:
    criticality_enum.create(op.get_bind(), checkfirst=True)
    op.add_column(
        "projects",
        sa.Column("criticality", criticality_enum, nullable=False, server_default="medium"),
    )
    # Drop the server_default after backfilling existing rows -- new
    # rows going forward always specify it explicitly via the ORM
    # model's Python-side default, matching the pattern already used
    # for is_active/role elsewhere.
    op.alter_column("projects", "criticality", server_default=None)


def downgrade() -> None:
    op.drop_column("projects", "criticality")
    criticality_enum.drop(op.get_bind(), checkfirst=True)
