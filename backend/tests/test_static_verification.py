"""
Stage 1 + Stage 2 static verification, wrapped as pytest tests.

These specifically avoid importing sqlalchemy/fastapi/alembic -- they
only use the stdlib `ast`-based checkers in scripts/, so they are real,
runnable checks even in an environment (like this sandbox) where the
third-party stack can't be installed. Once pytest is available, run
with `pytest tests/test_static_verification.py -v`.
"""
from __future__ import annotations

import importlib.util
import pathlib
import sys

BACKEND_DIR = pathlib.Path(__file__).resolve().parents[1]
SCRIPTS_DIR = BACKEND_DIR / "scripts"


def _load(module_name: str):
    spec = importlib.util.spec_from_file_location(module_name, SCRIPTS_DIR / f"{module_name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def test_model_consistency():
    module = _load("check_model_consistency")
    assert module.main() == 0, "domain model has a FK or relationship inconsistency -- see printed output above"


def test_migration_matches_models():
    module = _load("check_migration_matches_models")
    assert module.main() == 0, "the initial migration is out of sync with the domain models -- see printed output above"


def test_dependency_hygiene():
    module = _load("check_dependency_hygiene")
    assert module.main() == 0, "a forbidden raw-socket/packet-crafting/scanning package was detected"


def test_stage2_migration_chain_matches_models():
    module = _load("check_stage2_migration_chain_matches_models")
    assert module.main() == 0, "the full migration chain is out of sync with current domain models -- see printed output above"


def test_stage2_auth_security_invariants():
    module = _load("check_auth_security_invariants")
    assert module.main() == 0, "a Stage 2 authentication security invariant was violated -- see printed output above"


def test_column_drift():
    module = _load("check_column_drift")
    assert module.main() == 0, "a column mismatch was found between a domain model and the migration chain -- see printed output above"


def test_timeline_event_coverage():
    module = _load("check_timeline_event_coverage")
    assert module.main() == 0, "a TimelineEventTypeEnum value is neither used nor a documented exception -- see printed output above"


def test_intelligence_performance():
    module = _load("check_intelligence_performance")
    assert module.main() == 0, "pure Intelligence Engine logic did not complete within its performance budget -- see printed output above"


def test_route_authentication():
    module = _load("check_route_authentication")
    assert module.main() == 0, "a route handler is missing get_current_user/get_current_api_key and isn't a documented exemption -- see printed output above"


def test_router_registration():
    module = _load("check_router_registration")
    assert module.main() == 0, "a route module's router is defined but not registered in api/main.py -- see printed output above"


if __name__ == "__main__":
    # Runnable directly with plain `python3`, without pytest installed.
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS: {name}")
