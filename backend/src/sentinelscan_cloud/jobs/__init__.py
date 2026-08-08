"""Shared, job-handler-agnostic infrastructure for background job
execution (Section 9): failure classification and retry-with-backoff
policy. Deliberately has zero knowledge of any specific job (Report,
Intelligence Processing, or otherwise) -- intelligence/queue_registration.py
is where these pure primitives get applied to the one real job handler
that exists today, and any future job handler can reuse them the same
way without duplicating this logic.
"""
from __future__ import annotations
