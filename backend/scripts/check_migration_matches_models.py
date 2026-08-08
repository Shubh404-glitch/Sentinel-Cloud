"""
Static check: every table 0001_initial_schema.py's op.create_table(...)
calls create must have a matching domain model -- i.e. this migration
must never create a table that doesn't exist as a model (a real
typo/drift bug). Stdlib-only (ast), so it runs without SQLAlchemy/
Alembic installed.

This intentionally does NOT also require the reverse -- that every
model's table is created by 0001 specifically. That was true when this
script was written (0001 was the only migration in existence), but
stopped being the right question the moment Stage 2 added
0002_stage2_auth_schema.py: models are expected to outgrow what the
first migration alone created. The full-history version of that
question ("does the complete migration chain match today's models?")
is answered by scripts/check_stage2_migration_chain_matches_models.py.
"""
from __future__ import annotations

import ast
import pathlib
import sys

BACKEND_DIR = pathlib.Path(__file__).resolve().parents[1]
DOMAIN_DIR = BACKEND_DIR / "src" / "sentinelscan_cloud" / "domain"
MIGRATION_FILE = BACKEND_DIR / "alembic" / "versions" / "0001_initial_schema.py"


def _literal_str(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def model_tablenames() -> set[str]:
    names = set()
    for f in DOMAIN_DIR.glob("*.py"):
        if f.name in ("__init__.py", "base.py", "enums.py"):
            continue
        tree = ast.parse(f.read_text(), filename=str(f))
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign) and len(node.targets) == 1:
                target = node.targets[0]
                if isinstance(target, ast.Name) and target.id == "__tablename__":
                    lit = _literal_str(node.value)
                    if lit:
                        names.add(lit)
    return names


def migration_tablenames() -> set[str]:
    names = set()
    tree = ast.parse(MIGRATION_FILE.read_text(), filename=str(MIGRATION_FILE))
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            call_name = node.func.attr if isinstance(node.func, ast.Attribute) else None
            if call_name == "create_table" and node.args:
                lit = _literal_str(node.args[0])
                if lit:
                    names.add(lit)
    return names


def main() -> int:
    models = model_tablenames()
    migration = migration_tablenames()

    only_in_models = models - migration
    only_in_migration = migration - models

    print(f"Tables declared by models:    {len(models)}")
    print(f"Tables created by migration:  {len(migration)}")

    if only_in_models:
        print(
            f"NOTE (not a failure): in models but not created by 0001 -- expected once later "
            f"stages add their own migrations: {sorted(only_in_models)}"
        )
    if only_in_migration:
        print(f"MISMATCH -- created by 0001 but has no matching model: {sorted(only_in_migration)}")
        return 1

    print("PASSED -- every table 0001 creates has a matching model, no drift.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
