"""
Column-level drift checker between the domain models and the full
Alembic migration chain (0001 -> 0002 -> 0003 -> ...).

The existing checkers (check_migration_matches_models.py,
check_stage2_migration_chain_matches_models.py) only compare table
NAMES. Stage 3 only ever adds columns via op.add_column (assets.tags,
assets.extensions, findings.cve_ids, findings.signature,
findings.evidence, findings.correlation_fingerprint) -- exactly the
kind of change those two checkers cannot see. This script closes that
gap: it collects every column name per table from BOTH sources (models
via mapped_column ast parsing; migrations via create_table/add_column
ast parsing across every file in alembic/versions/) and diffs them,
per table. Stdlib-only (ast), so it runs without SQLAlchemy/Alembic
installed.
"""
from __future__ import annotations

import ast
import pathlib
import sys

BACKEND_DIR = pathlib.Path(__file__).resolve().parents[1]
DOMAIN_DIR = BACKEND_DIR / "src" / "sentinelscan_cloud" / "domain"
VERSIONS_DIR = BACKEND_DIR / "alembic" / "versions"


def _literal_str(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def model_columns() -> dict[str, set[str]]:
    """table_name -> set of column names, from every mapped_column(...)
    assignment on a class that also declares __tablename__."""
    tables: dict[str, set[str]] = {}
    for f in DOMAIN_DIR.glob("*.py"):
        if f.name in ("__init__.py", "base.py", "enums.py"):
            continue
        tree = ast.parse(f.read_text(), filename=str(f))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            tablename = None
            columns: set[str] = set()
            for stmt in node.body:
                if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1:
                    target = stmt.targets[0]
                    if isinstance(target, ast.Name) and target.id == "__tablename__":
                        tablename = _literal_str(stmt.value)
                if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
                    if isinstance(stmt.value, ast.Call):
                        call = stmt.value
                        call_name = call.func.id if isinstance(call.func, ast.Name) else (
                            call.func.attr if isinstance(call.func, ast.Attribute) else None
                        )
                        if call_name == "mapped_column":
                            columns.add(stmt.target.id)
            if tablename:
                tables.setdefault(tablename, set()).update(columns)
                # id/created_at/updated_at come from mixins (base.py), not
                # a mapped_column() call visible in this file -- add them
                # explicitly since every model has them.
                tables[tablename].update({"id", "created_at", "updated_at"})
    return tables


def _find_function_body(tree: ast.Module, function_name: str) -> list[ast.stmt]:
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == function_name:
            return node.body
    return []


def migration_columns() -> dict[str, set[str]]:
    """table_name -> set of column names, from every op.create_table(...)
    and op.add_column(...) call across the full migration chain (every
    file in alembic/versions/, not just one).

    Deliberately walks only each file's upgrade() function body, not the
    whole module -- downgrade() intentionally contains drop_column/
    drop_table calls that undo upgrade()'s changes, so scanning the
    entire module would have upgrade()'s additions immediately
    cancelled out by downgrade()'s drops appearing later in the same
    walk. (This was a real bug caught while building this checker --
    see the Stage 3 Completion Report.)
    """
    tables: dict[str, set[str]] = {}
    for f in sorted(VERSIONS_DIR.glob("*.py")):
        tree = ast.parse(f.read_text(), filename=str(f))
        upgrade_body = _find_function_body(tree, "upgrade")
        for stmt in upgrade_body:
            for node in ast.walk(stmt):
                if not isinstance(node, ast.Call):
                    continue
                call_name = node.func.attr if isinstance(node.func, ast.Attribute) else None

                if call_name == "create_table" and node.args:
                    table = _literal_str(node.args[0])
                    if not table:
                        continue
                    cols = set()
                    for arg in node.args[1:]:
                        if isinstance(arg, ast.Call):
                            col_call_name = arg.func.attr if isinstance(arg.func, ast.Attribute) else (
                                arg.func.id if isinstance(arg.func, ast.Name) else None
                            )
                            if col_call_name == "Column" and arg.args:
                                col_name = _literal_str(arg.args[0])
                                if col_name:
                                    cols.add(col_name)
                    tables.setdefault(table, set()).update(cols)

                if call_name == "add_column" and len(node.args) >= 2:
                    table = _literal_str(node.args[0])
                    col_arg = node.args[1]
                    if table and isinstance(col_arg, ast.Call):
                        col_call_name = col_arg.func.attr if isinstance(col_arg.func, ast.Attribute) else (
                            col_arg.func.id if isinstance(col_arg.func, ast.Name) else None
                        )
                        if col_call_name == "Column" and col_arg.args:
                            col_name = _literal_str(col_arg.args[0])
                            if col_name:
                                tables.setdefault(table, set()).add(col_name)

                if call_name == "drop_column" and len(node.args) >= 2:
                    # A column dropped by THIS SAME migration's upgrade()
                    # (a real rename-via-drop-add, not downgrade() undoing
                    # things) should still be subtracted.
                    table = _literal_str(node.args[0])
                    col_name = _literal_str(node.args[1])
                    if table and col_name and table in tables:
                        tables[table].discard(col_name)
    return tables


def main() -> int:
    models = model_columns()
    migrations = migration_columns()

    all_tables = sorted(set(models) | set(migrations))
    mismatches = []

    for table in all_tables:
        model_cols = models.get(table, set())
        migration_cols = migrations.get(table, set())
        only_in_model = model_cols - migration_cols
        only_in_migration = migration_cols - model_cols
        if only_in_model:
            mismatches.append(f"{table}: column(s) in model but not created by any migration: {sorted(only_in_model)}")
        if only_in_migration:
            mismatches.append(f"{table}: column(s) created by migration but not in model: {sorted(only_in_migration)}")

    print(f"Checked {len(all_tables)} tables across the full migration chain vs. the domain models.")
    if mismatches:
        print(f"FAILED -- {len(mismatches)} column-level mismatch(es):")
        for m in mismatches:
            print(f"  ✗ {m}")
        return 1

    total_columns = sum(len(c) for c in models.values())
    print(f"PASSED -- every column across {len(all_tables)} tables ({total_columns} columns total) matches "
          f"exactly between the domain models and the cumulative migration chain.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
