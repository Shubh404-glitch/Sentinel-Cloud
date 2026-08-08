"""
Correlation classification (Section 12.1): "classify each Finding as
new, resolved (present before, absent now), or recurring (present in
multiple consecutive reports)."

"Consecutive" (per the architecture's own wording) means this Asset's
immediately preceding Report, not its entire history -- so the
classification is always a two-way diff between the current report's
fingerprint set and the single previous report's fingerprint set for
the same Asset, not a full-history membership test. This module is that
diff, as a pure function; correlation/engine.py is the ORM-dependent
code that fetches the two fingerprint sets and applies the result.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ClassificationResult:
    new: frozenset[str] = field(default_factory=frozenset)
    recurring: frozenset[str] = field(default_factory=frozenset)
    resolved: frozenset[str] = field(default_factory=frozenset)


def classify_fingerprints(*, current: set[str], previous: set[str]) -> ClassificationResult:
    """
    current:  correlation_fingerprints of the Findings in the Report
              just ingested, for one Asset.
    previous: correlation_fingerprints of the Findings from that same
              Asset's immediately preceding Report (empty set if this
              is the first Report ever seen for this Asset).

    Returns which fingerprints are new (in current, not previous),
    recurring (in both), and resolved (in previous, not current).
    A resolved fingerprint reappearing in a later Report is correctly
    treated as `new` again by this same diff (it is not in the
    *immediately preceding* report, per the architecture's
    "consecutive" wording) -- it does not silently stay "resolved"
    forever, nor is it conflated with true recurrence.
    """
    return ClassificationResult(
        new=frozenset(current - previous),
        recurring=frozenset(current & previous),
        resolved=frozenset(previous - current),
    )
