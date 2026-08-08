"""Stage 8 threat intelligence and correlation schema."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0006_stage8_threat_intelligence"
down_revision = "0005_stage6_retry_fields"
branch_labels = None
depends_on = None


def upgrade():

    op.create_table(
        "cves",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("description", sa.Text()),
        sa.Column("published", sa.DateTime(timezone=True)),
        sa.Column("modified", sa.DateTime(timezone=True)),
        sa.Column("source", sa.String(100), nullable=False, server_default="curated"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "cvss",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("cve_id", sa.String(32), sa.ForeignKey("cves.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version", sa.String(20), nullable=False),
        sa.Column("base_score", sa.Float()),
        sa.Column("vector", sa.String(300)),
        sa.Column("severity", sa.String(30)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "cwes",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("name", sa.String(300), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "epss",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("cve_id", sa.String(32), sa.ForeignKey("cves.id", ondelete="CASCADE"), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("percentile", sa.Float()),
        sa.Column("timestamp", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "kevs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("cve_id", sa.String(32), sa.ForeignKey("cves.id", ondelete="CASCADE"), nullable=False),
        sa.Column("vendor", sa.String(300)),
        sa.Column("product", sa.String(500)),
        sa.Column("date_added", sa.DateTime(timezone=True)),
        sa.Column("due_date", sa.DateTime(timezone=True)),
        sa.Column("ransomware_use", sa.Boolean()),
        sa.Column("remediation", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "iocs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("value", sa.String(2048), nullable=False),
        sa.Column("type", sa.String(30), nullable=False),
        sa.Column("reputation", sa.String(50)),
        sa.Column("confidence", sa.Float()),
        sa.Column("source", sa.String(200), nullable=False),
        sa.Column("first_seen", sa.DateTime(timezone=True)),
        sa.Column("last_seen", sa.DateTime(timezone=True)),
        sa.Column("tags", postgresql.JSONB()),
        sa.Column("raw", postgresql.JSONB()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("organization_id", "value", "type", "source", name="uq_ioc_org_value_type_source"),
    )

    op.create_table(
        "mitre_tactics",
        sa.Column("id", sa.String(100), primary_key=True),
        sa.Column("name", sa.String(300), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "mitre_techniques",
        sa.Column("id", sa.String(100), primary_key=True),
        sa.Column("name", sa.String(300), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("tactic_id", sa.String(100), sa.ForeignKey("mitre_tactics.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "mitre_groups",
        sa.Column("id", sa.String(100), primary_key=True),
        sa.Column("name", sa.String(300), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "mitre_technique_groups",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("technique_id", sa.String(100), sa.ForeignKey("mitre_techniques.id", ondelete="CASCADE"), nullable=False),
        sa.Column("group_id", sa.String(100), sa.ForeignKey("mitre_groups.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("technique_id", "group_id", name="uq_mitre_technique_group"),
    )

    op.create_table(
        "vendor_advisories",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("advisory_id", sa.String(300), nullable=False),
        sa.Column("vendor", sa.String(200), nullable=False),
        sa.Column("title", sa.String(500)),
        sa.Column("url", sa.String(2000)),
        sa.Column("description", sa.Text()),
        sa.Column("published", sa.DateTime(timezone=True)),
        sa.Column("modified", sa.DateTime(timezone=True)),
        sa.Column("cve_ids", postgresql.JSONB()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("organization_id", "vendor", "advisory_id", name="uq_vendor_advisory_org_key"),
    )

    op.create_table(
        "exploit_availability",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("cve_id", sa.String(32), nullable=False),
        sa.Column("source", sa.String(200), nullable=False),
        sa.Column("available", sa.Boolean(), nullable=False),
        sa.Column("url", sa.String(2000)),
        sa.Column("confidence", sa.Float()),
        sa.Column("evidence", postgresql.JSONB()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("organization_id", "cve_id", "source", name="uq_exploit_org_cve_source"),
    )

    op.create_table(
        "correlation_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("finding_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("findings.id", ondelete="CASCADE"), nullable=False),
        sa.Column("intel_type", sa.String(60), nullable=False),
        sa.Column("intel_id", sa.String(300), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("relationship_type", sa.String(100), nullable=False),
        sa.Column("evidence", postgresql.JSONB()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("organization_id", "finding_id", "intel_type", "intel_id", name="uq_correlation_org_finding_intel"),
    )

    op.create_table(
        "related_finding_groups",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("label", sa.String(300)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "related_finding_group_members",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("group_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("related_finding_groups.id", ondelete="CASCADE"), nullable=False),
        sa.Column("finding_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("findings.id", ondelete="CASCADE"), nullable=False),
        sa.Column("relationship_type", sa.String(100), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("evidence", postgresql.JSONB()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("group_id", "finding_id", name="uq_related_group_finding"),
    )

    op.create_table(
        "attack_chains",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(300)),
        sa.Column("graph", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade():
    for t in [
        "attack_chains",
        "related_finding_group_members",
        "related_finding_groups",
        "correlation_results",
        "exploit_availability",
        "vendor_advisories",
        "mitre_technique_groups",
        "mitre_groups",
        "mitre_techniques",
        "mitre_tactics",
        "iocs",
        "kevs",
        "epss",
        "cwes",
        "cvss",
        "cves",
    ]:
        op.drop_table(t)    

