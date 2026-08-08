"""
Correlation preparation (Section 12.1, Stage 3 scope only).

Stage 3 computes and stores a stable fingerprint per Finding so that
Stage 4's actual Correlation module can later compare a new Report's
Findings against an Asset's prior Findings and classify each as new,
resolved, or recurring (that classification -- setting
Finding.is_new/is_resolved/is_recurring -- is explicitly Stage 4's job,
not this module's; see domain/finding.py's field comments).

Per the Report Export Schema v1 README, decision #7 (a Stage 3 design
decision confirmed, not left open): the fingerprint is always computed
by SentinelScan Cloud itself from data it already normalizes -- it
never trusts a producer-supplied `finding_ref` as the correlation key,
since that would let two different scanners' local ID schemes silently
collide or drift.
"""
from __future__ import annotations

import hashlib
import json


def compute_correlation_fingerprint(*, asset_identifier: str, title: str, signature: dict) -> str:
    """A stable, deterministic fingerprint for a Finding, scoped to one
    Asset. Built from:
      - asset_identifier: which Asset this is (an Asset's Findings are
        never compared against another Asset's).
      - normalized title: lowercased, whitespace-collapsed, so trivial
        capitalization/spacing differences between two reports of the
        same underlying issue don't produce different fingerprints.
      - signature: service/version/configuration_pattern, when
        present, sharpens the match (e.g. two different CVEs on the
        same asset with similar titles should NOT collide).

    Deliberately excludes: description (too free-form/verbose to be
    stable across re-scans), severity (a producer might re-score the
    same underlying issue differently between scans -- that's a
    legitimate change to surface via Correlation, not something that
    should mask the match), and any producer-supplied ref/ID.
    """
    normalized_title = " ".join(title.strip().lower().split())
    signature_key = json.dumps(_normalized_signature(signature), sort_keys=True)
    raw = f"{asset_identifier}\x1f{normalized_title}\x1f{signature_key}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _normalized_signature(signature: dict) -> dict:
    """Only the three known signature fields matter for fingerprinting;
    an unrecognized extra key (schema allows none here, but be
    defensive) must never silently change the fingerprint for
    unrelated reasons, and `None` and "missing" are treated the same
    so a producer that omits a field vs. sends it as null doesn't
    produce two different fingerprints for the same finding."""
    return {
        "service": (signature or {}).get("service") or None,
        "version": (signature or {}).get("version") or None,
        "configuration_pattern": (signature or {}).get("configuration_pattern") or None,
    }
