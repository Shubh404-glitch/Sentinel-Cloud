"""Provider-independent normalized records."""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

@dataclass(frozen=True)
class NormalizedCVE:
    id: str
    description: str | None = None
    published: datetime | None = None
    modified: datetime | None = None
    source: str = "unknown"
    cvss: list[dict[str, Any]] = field(default_factory=list)
    cwes: list[dict[str, Any]] = field(default_factory=list)

@dataclass(frozen=True)
class NormalizedEPSS:
    cve_id: str
    score: float
    percentile: float | None = None
    timestamp: datetime | None = None
    source: str = "epss"

@dataclass(frozen=True)
class NormalizedKEV:
    cve_id: str
    vendor: str | None = None
    product: str | None = None
    date_added: datetime | None = None
    due_date: datetime | None = None
    ransomware_use: bool | None = None
    remediation: str | None = None

@dataclass(frozen=True)
class NormalizedIOC:
    value: str
    type: str
    reputation: str
    confidence: float | None = None
    source: str = "unknown"
    tags: list[str] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class NormalizedVendorAdvisory:
    advisory_id: str
    vendor: str
    title: str | None = None
    url: str | None = None
    description: str | None = None
    published: datetime | None = None
    modified: datetime | None = None
    cve_ids: list[str] = field(default_factory=list)

@dataclass(frozen=True)
class NormalizedExploitAvailability:
    cve_id: str
    source: str
    available: bool
    url: str | None = None
    confidence: float | None = None
    evidence: dict[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class NormalizedMitreTechnique:
    id: str
    name: str
    description: str | None = None
    tactic_ids: list[str] = field(default_factory=list)

@dataclass(frozen=True)
class ProviderResult:
    records: list[Any]
    source: str
    warnings: list[str] = field(default_factory=list)
