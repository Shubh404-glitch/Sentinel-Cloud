"""
Central import point for every domain entity (Section 10).

Alembic imports Base from here so importing this module registers every
SQLAlchemy model into Base.metadata.
"""

from __future__ import annotations

from sentinelscan_cloud.domain.base import Base

# Import APIKey first because Organization references it
from sentinelscan_cloud.domain.api_key import APIKey

from sentinelscan_cloud.domain.organization import Organization
from sentinelscan_cloud.domain.user import User
from sentinelscan_cloud.domain.project import Project
from sentinelscan_cloud.domain.asset import Asset
from sentinelscan_cloud.domain.report import Report
from sentinelscan_cloud.domain.report_asset import ReportAsset
from sentinelscan_cloud.domain.finding import Finding
from sentinelscan_cloud.domain.recommendation import (
    Recommendation,
    RecommendationFinding,
)
from sentinelscan_cloud.domain.security_score_snapshot import SecurityScoreSnapshot
from sentinelscan_cloud.domain.timeline_event import TimelineEvent
from sentinelscan_cloud.domain.threat_reference_entry import ThreatReferenceEntry
from sentinelscan_cloud.domain.audit_log_entry import AuditLogEntry
from sentinelscan_cloud.domain.refresh_token import RefreshToken

# Stage 8 Threat Intelligence
from sentinelscan_cloud.domain.threat_intel_vuln import (
    CVE,
    CVSS,
    CWE,
    EPSS,
    KEV,
    VendorAdvisory,
    ExploitAvailability,
)

from sentinelscan_cloud.domain.threat_intel_ioc import IOC

from sentinelscan_cloud.domain.mitre_attack import (
    MitreTactic,
    MitreTechnique,
    MitreGroup,
    MitreTechniqueGroup,
)

from sentinelscan_cloud.domain.correlation import (
    CorrelationResult,
    RelatedFindingGroup,
    RelatedFindingGroupMember,
    AttackChain,
)


__all__ = [
    "Base",

    # Core
    "Organization",
    "User",
    "Project",
    "Asset",
    "Report",
    "ReportAsset",
    "Finding",
    "Recommendation",
    "RecommendationFinding",
    "SecurityScoreSnapshot",
    "TimelineEvent",
    "ThreatReferenceEntry",

    # Authentication
    "APIKey",
    "AuditLogEntry",
    "RefreshToken",

    # Vulnerability Intelligence
    "CVE",
    "CVSS",
    "CWE",
    "EPSS",
    "KEV",
    "VendorAdvisory",
    "ExploitAvailability",

    # IOC
    "IOC",

    # MITRE ATT&CK
    "MitreTactic",
    "MitreTechnique",
    "MitreGroup",
    "MitreTechniqueGroup",

    # Correlation
    "CorrelationResult",
    "RelatedFindingGroup",
    "RelatedFindingGroupMember",
    "AttackChain",
]