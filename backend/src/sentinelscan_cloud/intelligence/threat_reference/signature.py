"""
Threat Reference Correlation (Section 12.5): "match Finding signatures
(service + version + configuration pattern) against SentinelScan
Cloud's curated reference knowledge base."

ThreatReferenceEntry.signature (Section 10) is a single, unique string
column -- this module is the one place that turns a Finding's
structured signature dict (service/version/configuration_pattern) into
that same canonical string shape, so building a ThreatReferenceEntry
and matching a Finding against one always agree on the format.
"""
from __future__ import annotations


def build_canonical_signature(signature: dict) -> str:
    """Deterministic, case-insensitive canonical form. A missing field
    and an explicit null are treated identically (both become the
    empty placeholder), matching correlation_prep.py's same choice for
    the same reason: a producer omitting a field vs. sending it null
    must not change matching behavior."""
    service = (signature or {}).get("service") or ""
    version = (signature or {}).get("version") or ""
    configuration_pattern = (signature or {}).get("configuration_pattern") or ""
    return f"{service.strip().lower()}:{version.strip().lower()}:{configuration_pattern.strip().lower()}"


def is_signature_matchable(signature: dict) -> bool:
    """A signature with no service at all is too weak to usefully
    match against the reference knowledge base (an empty
    "::"-shaped canonical string would otherwise spuriously match a
    ThreatReferenceEntry someone mistakenly created with no service
    either) -- Stage 4 skips matching entirely rather than risk a
    false-positive correlation."""
    return bool((signature or {}).get("service"))
