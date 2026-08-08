"""
Enums shared across domain entities.

Role is deliberately a small, fixed set for v1 (see the architecture's
Section 10 review: "Organization / User / Role scope for v1") rather than
a full custom-role/permission-matrix table -- the column can grow its
set of values later without a schema change.
"""
from __future__ import annotations

import enum


class RoleEnum(str, enum.Enum):
    ADMIN = "admin"      # manage Users, ApiKeys, Projects within the Organization
    MEMBER = "member"    # view and act on intelligence output, cannot manage the Organization


class SourceEditionEnum(str, enum.Enum):
    """Which SentinelScan product produced an ingested Report (Section 6.1,
    Section 11 step 4: source-edition detection)."""

    DISCOVER = "discover"
    OPERATE = "operate"


class SeverityEnum(str, enum.Enum):
    """Matches the weighted RiskLevel scale already established across the
    SentinelScan ecosystem (Section 12.2: Risk Scoring)."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ReportProcessingStatusEnum(str, enum.Enum):
    """Status shown in the Activity Center / Report Center as an
    Intelligence Processing job progresses (Section 11 step 9).

    Stage 6 addition: RETRYING and PERMANENTLY_FAILED. Before Stage 6,
    intelligence/pipeline.py's run_intelligence_processing caught every
    exception identically and marked FAILED -- no distinction between
    "a bug in the data/code, will never succeed no matter how many
    times we try" and "a transient blip (e.g. a dropped DB connection)
    that would likely succeed on retry." Section 9 already described
    the intended behavior ("retried with backoff on transient failure,
    but a deterministic failure is marked failed ... not retried
    forever") but nothing implemented the distinction. See
    jobs/failure_classification.py and
    intelligence/queue_registration.py's retry wrapper.

    State mapping (no PENDING/RUNNING split -- a Report is marked
    PROCESSING synchronously at ingestion time, before the job even
    runs, so there is no window where a Report exists but is merely
    "pending"; PROCESSING already covers both):
      PROCESSING          -- pending or actively running (unchanged).
      COMPLETE            -- succeeded (unchanged).
      FAILED              -- failed on the FIRST attempt with a
                             deterministic error, or an unclassifiable/
                             unknown exception (fail-safe default --
                             see failure_classification.py). No retry
                             was attempted.
      RETRYING            -- a transient error occurred and at least one
                             more retry attempt is scheduled.
      PERMANENTLY_FAILED  -- a transient error occurred but every retry
                             attempt also failed; retries are exhausted.
    """

    PROCESSING = "processing"
    COMPLETE = "complete"
    FAILED = "failed"
    RETRYING = "retrying"
    PERMANENTLY_FAILED = "permanently_failed"


class TimelineEventTypeEnum(str, enum.Enum):
    """The discrete, dated changes a TimelineEvent can represent
    (Section 10: TimelineEvent; Section 12.1: Correlation).

    ASSET_REMOVED is intentionally not emitted anywhere yet: an Asset
    missing from the latest Report does not reliably mean it was
    removed from the infrastructure -- it may simply be outside this
    particular scan's scope, or the scan may have failed to reach it
    that one time. Inferring removal from a single absence risks a
    false "asset removed" event. This value is reserved for an
    explicit removal action (e.g. a user archiving an Asset in a
    future UI, or a producer-side signal the schema doesn't carry
    today) rather than a heuristic Stage 4 would have to guess at."""

    FINDING_NEW = "finding_new"
    FINDING_RESOLVED = "finding_resolved"
    FINDING_RECURRING = "finding_recurring"
    ASSET_ADDED = "asset_added"
    ASSET_REMOVED = "asset_removed"
    SCORE_CHANGED = "score_changed"


class SecurityScoreScopeEnum(str, enum.Enum):
    """A SecurityScoreSnapshot can be produced at any of these three
    rollup levels (Section 10: SecurityScoreSnapshot; Section 12.2)."""

    ASSET = "asset"
    PROJECT = "project"
    ORGANIZATION = "organization"


class CriticalityEnum(str, enum.Enum):
    """Stage 4 addition (Section 12.3: Prioritization ranks
    Recommendations using, among other inputs, "Asset criticality (a
    Project-level setting)") -- the architecture names this input but
    no column existed anywhere for it (Stage 1/2/3 didn't need it).
    Added on Project, not Asset, exactly as Section 12.3 specifies."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
