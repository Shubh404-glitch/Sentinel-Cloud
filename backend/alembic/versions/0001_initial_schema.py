"""initial schema -- Section 10 domain model

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-07-17 00:00:00

NOTE ON HOW THIS FILE WAS PRODUCED (read before running):
This sandbox has no network access, so Alembic itself could not be
installed and `alembic revision --autogenerate` could not actually be
run against a live database. This migration was instead hand-authored
directly from the domain models in src/sentinelscan_cloud/domain/, in
the same table/column/constraint shape autogenerate would produce.
Before relying on this in a real environment, run
`alembic revision --autogenerate -m "check"` against an EMPTY database
with these models importable, and confirm it detects no further changes
-- see the Stage 1 Completion Report for the exact command.
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[Sequence[str], None] = None
depends_on: Union[Sequence[str], None] = None


def upgrade() -> None:
    # --- organizations (Section 10: top-level tenant boundary) ---
    op.create_table(
        "organizations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(255), nullable=False),
    )
    op.create_index("ix_organizations_slug", "organizations", ["slug"], unique=True)

    # --- users ---
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("display_name", sa.String(255), nullable=False),
        sa.Column("role", sa.Enum("admin", "member", name="role_enum"), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
    )
    op.create_index("ix_users_organization_id", "users", ["organization_id"])
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    # --- projects ---
    op.create_table(
        "projects",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
    )
    op.create_index("ix_projects_organization_id", "projects", ["organization_id"])

    # --- api_keys ---
    op.create_table(
        "api_keys",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("hashed_key", sa.String(255), nullable=False),
        sa.Column("key_prefix", sa.String(16), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_api_keys_organization_id", "api_keys", ["organization_id"])
    op.create_index("ix_api_keys_hashed_key", "api_keys", ["hashed_key"], unique=True)

    # --- assets (current_security_score_snapshot_id FK added later: circular w/ security_score_snapshots) ---
    op.create_table(
        "assets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("identifier", sa.String(255), nullable=False),
        sa.Column("display_name", sa.String(255), nullable=True),
        sa.Column("current_security_score_snapshot_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index("ix_assets_project_id", "assets", ["project_id"])
    op.create_index("ix_assets_identifier", "assets", ["identifier"])

    # --- reports ---
    op.create_table(
        "reports",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_edition", sa.Enum("discover", "operate", name="source_edition_enum"), nullable=False),
        sa.Column("schema_version", sa.String(32), nullable=False),
        sa.Column("raw_blob_storage_key", sa.String(1024), nullable=False),
        sa.Column(
            "processing_status",
            sa.Enum("processing", "complete", "failed", name="report_processing_status_enum"),
            nullable=False,
        ),
        sa.Column("processing_failure_reason", sa.String(2048), nullable=True),
        sa.Column("ingested_via_api_key_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("api_keys.id", ondelete="SET NULL"), nullable=True),
    )

    # --- report_assets (join: Report <-> Asset) ---
    op.create_table(
        "report_assets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("report_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("reports.id", ondelete="CASCADE"), nullable=False),
        sa.Column("asset_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("assets.id", ondelete="CASCADE"), nullable=False),
        sa.UniqueConstraint("report_id", "asset_id", name="uq_report_asset"),
    )
    op.create_index("ix_report_assets_report_id", "report_assets", ["report_id"])
    op.create_index("ix_report_assets_asset_id", "report_assets", ["asset_id"])

    # --- threat_reference_entries ---
    op.create_table(
        "threat_reference_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("signature", sa.String(500), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("known_risk_context", sa.Text(), nullable=False),
    )
    op.create_index("ix_threat_reference_entries_signature", "threat_reference_entries", ["signature"], unique=True)

    # --- findings ---
    op.create_table(
        "findings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("report_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("reports.id", ondelete="CASCADE"), nullable=False),
        sa.Column("asset_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("assets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("threat_reference_entry_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("threat_reference_entries.id", ondelete="SET NULL"), nullable=True),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("severity", sa.Enum("low", "medium", "high", "critical", name="severity_enum"), nullable=False),
        sa.Column("source_recommendation_text", sa.Text(), nullable=True),
        sa.Column("is_new", sa.Boolean(), nullable=True),
        sa.Column("is_resolved", sa.Boolean(), nullable=True),
        sa.Column("is_recurring", sa.Boolean(), nullable=True),
    )
    op.create_index("ix_findings_report_id", "findings", ["report_id"])
    op.create_index("ix_findings_asset_id", "findings", ["asset_id"])

    # --- recommendations ---
    op.create_table(
        "recommendations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("asset_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("assets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("priority_rank", sa.Integer(), nullable=False),
    )
    op.create_index("ix_recommendations_asset_id", "recommendations", ["asset_id"])

    # --- recommendation_findings (join: Recommendation <-> Finding) ---
    op.create_table(
        "recommendation_findings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("recommendation_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("recommendations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("finding_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("findings.id", ondelete="CASCADE"), nullable=False),
    )
    op.create_index("ix_recommendation_findings_recommendation_id", "recommendation_findings", ["recommendation_id"])
    op.create_index("ix_recommendation_findings_finding_id", "recommendation_findings", ["finding_id"])

    # --- security_score_snapshots ---
    op.create_table(
        "security_score_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("scope", sa.Enum("asset", "project", "organization", name="security_score_scope_enum"), nullable=False),
        sa.Column("asset_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("assets.id", ondelete="CASCADE"), nullable=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("contributing_factors", postgresql.JSONB(), nullable=False),
    )
    op.create_index("ix_security_score_snapshots_asset_id", "security_score_snapshots", ["asset_id"])
    op.create_index("ix_security_score_snapshots_project_id", "security_score_snapshots", ["project_id"])
    op.create_index("ix_security_score_snapshots_organization_id", "security_score_snapshots", ["organization_id"])

    # --- assets.current_security_score_snapshot_id FK (added now that both tables exist -- use_alter in the model) ---
    op.create_foreign_key(
        "fk_assets_current_score_snapshot",
        "assets",
        "security_score_snapshots",
        ["current_security_score_snapshot_id"],
        ["id"],
    )

    # --- timeline_events ---
    op.create_table(
        "timeline_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("asset_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("assets.id", ondelete="CASCADE"), nullable=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=True),
        sa.Column(
            "event_type",
            sa.Enum(
                "finding_new", "finding_resolved", "finding_recurring",
                "asset_added", "asset_removed", "score_changed",
                name="timeline_event_type_enum",
            ),
            nullable=False,
        ),
        sa.Column("summary", sa.String(1000), nullable=False),
    )
    op.create_index("ix_timeline_events_asset_id", "timeline_events", ["asset_id"])
    op.create_index("ix_timeline_events_project_id", "timeline_events", ["project_id"])

    # --- audit_log_entries ---
    op.create_table(
        "audit_log_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("api_key_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("api_keys.id", ondelete="SET NULL"), nullable=True),
        sa.Column("action", sa.String(255), nullable=False),
        sa.Column("affected_entity_type", sa.String(100), nullable=False),
        sa.Column("affected_entity_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(), nullable=False),
    )
    op.create_index("ix_audit_log_entries_organization_id", "audit_log_entries", ["organization_id"])
    op.create_index("ix_audit_log_entries_user_id", "audit_log_entries", ["user_id"])
    op.create_index("ix_audit_log_entries_api_key_id", "audit_log_entries", ["api_key_id"])


def downgrade() -> None:
    op.drop_table("audit_log_entries")
    op.drop_table("timeline_events")
    op.drop_constraint("fk_assets_current_score_snapshot", "assets", type_="foreignkey")
    op.drop_table("security_score_snapshots")
    op.drop_table("recommendation_findings")
    op.drop_table("recommendations")
    op.drop_table("findings")
    op.drop_table("threat_reference_entries")
    op.drop_table("report_assets")
    op.drop_table("reports")
    op.drop_table("assets")
    op.drop_table("api_keys")
    op.drop_table("projects")
    op.drop_table("users")
    op.drop_table("organizations")

    # Enum types are dropped automatically by drop_table on Postgres only
    # if no column references them; drop explicitly to be safe.
    sa.Enum(name="timeline_event_type_enum").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="security_score_scope_enum").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="severity_enum").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="report_processing_status_enum").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="source_edition_enum").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="role_enum").drop(op.get_bind(), checkfirst=True)
