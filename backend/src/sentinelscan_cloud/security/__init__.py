"""Low-level security primitives for Stage 2 (Section 9: Authentication;
Section 15: Security Considerations).

Nothing in this package talks to the database or FastAPI -- it is pure,
dependency-light cryptographic and token machinery, so the higher-level
service/dependency layers can be tested and reasoned about without
re-deriving hashing or token semantics themselves.
"""
from __future__ import annotations
