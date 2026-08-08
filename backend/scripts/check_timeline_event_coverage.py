"""
Static check: every value of TimelineEventTypeEnum (domain/enums.py)
must actually be used somewhere under src/sentinelscan_cloud/ingestion/
or src/sentinelscan_cloud/intelligence/ -- catches an enum value that
was defined (Stage 3) but never actually wired up to emit a
TimelineEvent (a real risk once ASSET_REMOVED/SCORE_CHANGED are added
without a caller, for example). Stdlib-only (ast + grep-style text
search), no SQLAlchemy needed.
"""
from __future__ import annotations

import ast
import pathlib
import sys

BACKEND_DIR = pathlib.Path(__file__).resolve().parents[1]
ENUMS_FILE = BACKEND_DIR / "src" / "sentinelscan_cloud" / "domain" / "enums.py"
SEARCH_DIRS = [
    BACKEND_DIR / "src" / "sentinelscan_cloud" / "ingestion",
    BACKEND_DIR / "src" / "sentinelscan_cloud" / "intelligence",
]


def timeline_event_type_values() -> list[str]:
    tree = ast.parse(ENUMS_FILE.read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "TimelineEventTypeEnum":
            values = []
            for stmt in node.body:
                if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1:
                    values.append(stmt.targets[0].id)
            return values
    raise RuntimeError("TimelineEventTypeEnum not found in domain/enums.py")


def main() -> int:
    values = timeline_event_type_values()
    all_source = ""
    for d in SEARCH_DIRS:
        for f in d.rglob("*.py"):
            all_source += f.read_text()

    # Documented, reasoned exception -- see TimelineEventTypeEnum's own
    # docstring in domain/enums.py for why ASSET_REMOVED is reserved,
    # not wired to a heuristic. Anything else unused is a real gap.
    expected_unused = {"ASSET_REMOVED"}

    print(f"TimelineEventTypeEnum defines {len(values)} value(s): {values}")
    unused = {v for v in values if f"TimelineEventTypeEnum.{v}" not in all_source}
    unexpected_unused = unused - expected_unused

    if unexpected_unused:
        print(f"FAILED -- {len(unexpected_unused)} value(s) defined but never constructed anywhere: {sorted(unexpected_unused)}")
        return 1

    if unused:
        print(f"NOTE (not a failure): {sorted(unused)} intentionally unused -- see domain/enums.py docstring.")
    print("PASSED -- every TimelineEventTypeEnum value is either used, or a documented, reasoned exception.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
