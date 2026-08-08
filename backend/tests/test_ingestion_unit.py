"""
Stage 3 unit tests for everything that has NO SQLAlchemy/FastAPI/DB
dependency: schema validation, both parsers, source-edition dispatch,
correlation fingerprinting, identifier canonicalization, local object
storage, and the in-process job queue.

Genuinely runnable in this sandbox right now (unlike
test_ingestion_integration.py, which needs a real Postgres + the full
dependency stack) -- run directly with `python3 tests/test_ingestion_unit.py`
or, once pytest is installed, `pytest tests/test_ingestion_unit.py -v`.
"""
from __future__ import annotations

import asyncio
import copy
import json
import pathlib
import tempfile

from sentinelscan_cloud.ingestion.correlation_prep import compute_correlation_fingerprint
from sentinelscan_cloud.ingestion.errors import (
    IngestionError,
    SchemaValidationError,
    StructuralValidationError,
    UnknownSourceEditionError,
    UnsupportedSchemaVersionError,
)
from sentinelscan_cloud.ingestion.job_queue import InProcessJobQueue
from sentinelscan_cloud.ingestion.object_storage import LocalFilesystemObjectStorage
from sentinelscan_cloud.ingestion.parsers.common import canonicalize_identifier, parsed_report_from_validated_payload
from sentinelscan_cloud.ingestion.parsers.discover_parser import parse_discover_report
from sentinelscan_cloud.ingestion.parsers.operate_parser import parse_operate_report
from sentinelscan_cloud.ingestion.report_dispatch import parse_report
from sentinelscan_cloud.ingestion.schema_validation.validator import SCHEMA_DIR, validate_report_payload

EXAMPLES_DIR = SCHEMA_DIR / "v1" / "examples"


def _load_example(name: str) -> dict:
    return json.loads((EXAMPLES_DIR / name).read_text())


# --- schema validation ---

def test_both_examples_validate():
    validate_report_payload(_load_example("discover_example.json"))
    validate_report_payload(_load_example("operate_example.json"))


def test_missing_required_field_rejected():
    bad = _load_example("discover_example.json")
    del bad["scan"]
    try:
        validate_report_payload(bad)
        assert False, "should have raised"
    except SchemaValidationError:
        pass


def test_invalid_enum_value_rejected():
    bad = _load_example("discover_example.json")
    bad["findings"][0]["severity"] = "catastrophic"
    try:
        validate_report_payload(bad)
        assert False, "should have raised"
    except SchemaValidationError:
        pass


def test_unsupported_major_version_rejected():
    bad = _load_example("discover_example.json")
    bad["schema_version"] = "2.0"
    try:
        validate_report_payload(bad)
        assert False, "should have raised"
    except UnsupportedSchemaVersionError:
        pass


def test_minor_version_bump_still_validates():
    good = _load_example("discover_example.json")
    good["schema_version"] = "1.1"
    validate_report_payload(good)


def test_oversized_field_rejected_not_truncated():
    bad = _load_example("discover_example.json")
    bad["findings"][0]["title"] = "A" * 600
    try:
        validate_report_payload(bad)
        assert False, "should have raised"
    except SchemaValidationError:
        pass


def test_unexpected_top_level_property_rejected():
    bad = _load_example("discover_example.json")
    bad["unexpected_field"] = "nope"
    try:
        validate_report_payload(bad)
        assert False, "should have raised"
    except SchemaValidationError:
        pass


# --- parsers + dispatch ---

def test_discover_parser_parses_real_example():
    raw = (EXAMPLES_DIR / "discover_example.json").read_bytes()
    parsed = parse_discover_report(raw)
    assert parsed.source_edition == "discover"
    assert len(parsed.assets) == 2
    assert len(parsed.findings) == 2
    assert parsed.asset_by_ref()["asset-1"].identifier == "10.20.30.40"


def test_operate_parser_parses_real_example():
    raw = (EXAMPLES_DIR / "operate_example.json").read_bytes()
    parsed = parse_operate_report(raw)
    assert parsed.source_edition == "operate"
    assert len(parsed.assets) == 1


def test_discover_parser_rejects_wrong_edition():
    payload = _load_example("operate_example.json")
    try:
        parse_discover_report(json.dumps(payload).encode())
        assert False, "should have raised"
    except StructuralValidationError:
        pass


def test_dispatch_routes_by_source_edition():
    for name in ("discover_example.json", "operate_example.json"):
        raw = (EXAMPLES_DIR / name).read_bytes()
        parsed = parse_report(raw)
        assert parsed.source_edition in ("discover", "operate")


def test_dispatch_rejects_unknown_edition():
    try:
        parse_report(b'{"source_edition": "nmap"}')
        assert False, "should have raised"
    except UnknownSourceEditionError:
        pass


def test_dispatch_rejects_non_json():
    try:
        parse_report(b"not json at all {{{")
        assert False, "should have raised"
    except StructuralValidationError:
        pass


def test_parsed_report_from_validated_payload_shape():
    payload = _load_example("discover_example.json")
    parsed = parsed_report_from_validated_payload(payload)
    assert parsed.findings[0].cve_ids == ["CVE-2023-5678", "CVE-2024-0727"]
    assert parsed.findings[1].signature["configuration_pattern"] == "ssl=off"


# --- correlation fingerprint ---

def test_fingerprint_stable_across_whitespace_and_case():
    fp1 = compute_correlation_fingerprint(
        asset_identifier="10.20.30.40", title="Outdated OpenSSL version",
        signature={"service": "openssl", "version": "1.1.1w", "configuration_pattern": None},
    )
    fp2 = compute_correlation_fingerprint(
        asset_identifier="10.20.30.40", title="  outdated   OPENSSL Version  ",
        signature={"service": "openssl", "version": "1.1.1w", "configuration_pattern": None},
    )
    assert fp1 == fp2
    assert len(fp1) == 64


def test_fingerprint_differs_by_asset_and_signature():
    base = dict(asset_identifier="10.20.30.40", title="X", signature={"service": "a"})
    fp_base = compute_correlation_fingerprint(**base)
    fp_other_asset = compute_correlation_fingerprint(**{**base, "asset_identifier": "10.20.30.99"})
    fp_other_sig = compute_correlation_fingerprint(**{**base, "signature": {"service": "b"}})
    assert fp_base != fp_other_asset
    assert fp_base != fp_other_sig


def test_fingerprint_empty_and_null_signature_equivalent():
    fp_empty = compute_correlation_fingerprint(asset_identifier="a", title="t", signature={})
    fp_null = compute_correlation_fingerprint(
        asset_identifier="a", title="t", signature={"service": None, "version": None, "configuration_pattern": None}
    )
    assert fp_empty == fp_null


# --- identifier canonicalization (both import paths, same function) ---

def test_canonicalize_identifier_hostname_fqdn_lowercased():
    assert canonicalize_identifier("DB01.Internal.EXAMPLE.com", "fqdn") == "db01.internal.example.com"
    assert canonicalize_identifier("  MyHost  ", "hostname") == "myhost"


def test_canonicalize_identifier_ip_left_as_is():
    assert canonicalize_identifier("10.20.30.40", "ip_v4") == "10.20.30.40"


# --- object storage ---

def test_local_object_storage_roundtrip():
    with tempfile.TemporaryDirectory() as tmp:
        storage = LocalFilesystemObjectStorage(pathlib.Path(tmp) / "reports")
        key = "org-1/reports/report-1.json"
        storage.put(key, b'{"a": 1}')
        assert storage.exists(key)
        assert storage.get(key) == b'{"a": 1}'
        assert not storage.exists("does-not-exist")


def test_local_object_storage_rejects_path_traversal():
    with tempfile.TemporaryDirectory() as tmp:
        storage = LocalFilesystemObjectStorage(pathlib.Path(tmp) / "reports")
        try:
            storage.put("../../../etc/passwd", b"pwned")
            assert False, "should have raised"
        except ValueError:
            pass


# --- job queue ---

def test_in_process_job_queue_runs_handler():
    calls = []
    queue = InProcessJobQueue()
    queue.register_handler("job", lambda payload: calls.append(payload))
    job_id = asyncio.run(queue.enqueue("job", {"x": 1}))
    assert calls == [{"x": 1}]
    assert len(job_id) == 32


def test_in_process_job_queue_unregistered_job_is_safe_noop():
    queue = InProcessJobQueue()
    job_id = asyncio.run(queue.enqueue("nothing_registered", {}))
    assert len(job_id) == 32


def test_in_process_job_queue_propagates_handler_exception():
    queue = InProcessJobQueue()
    queue.register_handler("boom", lambda payload: (_ for _ in ()).throw(ValueError("fail")))
    try:
        asyncio.run(queue.enqueue("boom", {}))
        assert False, "should have raised"
    except ValueError:
        pass


def test_in_process_job_queue_supports_async_handler():
    """Stage 4 fix: the real Intelligence Processing handler is async
    (needs to await an AsyncSession) -- enqueue() must await it, not
    just call it and ignore the returned coroutine."""
    calls = []

    async def async_handler(payload):
        calls.append(payload)

    queue = InProcessJobQueue()
    queue.register_handler("async_job", async_handler)
    job_id = asyncio.run(queue.enqueue("async_job", {"report_id": "abc"}))
    assert calls == [{"report_id": "abc"}]
    assert len(job_id) == 32


if __name__ == "__main__":
    # Runnable directly with plain `python3`, without pytest installed.
    ran, failed = 0, 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            ran += 1
            try:
                fn()
                print(f"PASS: {name}")
            except AssertionError as e:
                failed += 1
                print(f"FAIL: {name}: {e}")
    print(f"\n{ran - failed}/{ran} passed")
    if failed:
        raise SystemExit(1)
