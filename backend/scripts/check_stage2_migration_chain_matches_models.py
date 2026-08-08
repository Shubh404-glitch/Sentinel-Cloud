"""Stage 2 static check: the CUMULATIVE set of tables created across every
migration file in alembic/versions/ must match exactly the set of
tables the domain models declare -- no more, no fewer.

This is deliberately a NEW script, not an edit to
check_migration_matches_models.py. That script is hard-scoped to
0001_initial_schema.py by design and correctly continues to check "does
migration 0001 alone match the models it was written against" --
editing it to scan all migrations would silently change what a Stage 1
script promises to verify. This script instead answers the Stage
2-and-onward question: "does the full migration history, applied in
order, match the current models?"

Stdlib-only (ast), so it runs without SQLAlchemy/Alembic installed --
same sandbox constraint documented in 0001_initial_schema.py and
0002_stage2_auth_schema.py.
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


def _revision_ids(tree: ast.Module) -> tuple[str | None, str | None]:
    revision, down_revision = None, None
    for node in ast.walk(tree):
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if node.target.id == "revision" and node.value is not None:
                revision = _literal_str(node.value)
            if node.target.id == "down_revision" and node.value is not None:
                down_revision = _literal_str(node.value)
    return revision, down_revision


def _tables_created_and_dropped(tree: ast.Module) -> tuple[set[str], set[str]]:
    """Only inspects the `upgrade()` function body. Scanning the whole
    module (including `downgrade()`) was an earlier bug in this script:
    every drop_table(...) call in downgrade() was being counted as if
    it happened during upgrade, cancelling out that migration's own
    create_table(...) calls and making every migration look like it
    creates nothing. Caught by testing this script against the real
    migration chain before relying on it -- see the Stage 2 Completion
    Report."""
    created, dropped = set(), set()
    upgrade_fn = next(
        (n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "upgrade"),
        None,
    )
    if upgrade_fn is None:
        return created, dropped

    for node in ast.walk(upgrade_fn):
        if isinstance(node, ast.Call):
            call_name = node.func.attr if isinstance(node.func, ast.Attribute) else None
            if call_name == "create_table" and node.args:
                lit = _literal_str(node.args[0])
                if lit:
                    created.add(lit)
            if call_name == "drop_table" and node.args:
                lit = _literal_str(node.args[0])
                if lit:
                    dropped.add(lit)
    return created, dropped


def ordered_migration_chain() -> list[pathlib.Path]:
    """Walk migration files by revision/down_revision linkage (not
    filename sort) so the chain is verified the same way Alembic itself
    would apply it."""
    files = sorted(VERSIONS_DIR.glob("*.py"))
    by_revision: dict[str, pathlib.Path] = {}
    down_revision_of: dict[str, str | None] = {}

    for f in files:
        tree = ast.parse(f.read_text(), filename=str(f))
        revision, down_revision = _revision_ids(tree)
        if revision is None:
            continue
        by_revision[revision] = f
        down_revision_of[revision] = down_revision

    # Find the head: a revision that no other revision declares as its down_revision.
    all_down_revisions = set(down_revision_of.values())
    heads = [rev for rev in by_revision if rev not in all_down_revisions]
    if len(heads) != 1:
        print(f"WARNING: expected exactly one migration head, found {heads!r} -- falling back to filename order")
        return files

    chain: list[pathlib.Path] = []
    current: str | None = heads[0]
    seen: set[str] = set()
    while current is not None:
        if current in seen:
            print(f"WARNING: cycle detected in migration chain at {current!r} -- falling back to filename order")
            return files
        seen.add(current)
        chain.append(by_revision[current])
        current = down_revision_of[current]

    chain.reverse()  # root-first, matching upgrade order
    return chain


def cumulative_migration_tablenames() -> set[str]:
    tables: set[str] = set()
    for f in ordered_migration_chain():
        tree = ast.parse(f.read_text(), filename=str(f))
        created, dropped = _tables_created_and_dropped(tree)
        tables |= created
        tables -= dropped
    return tables


def main() -> int:
    models = model_tablenames()
    migrations = cumulative_migration_tablenames()

    only_in_models = models - migrations
    only_in_migrations = migrations - models

    print(f"Tables declared by models:                 {len(models)}")
    print(f"Tables created by full migration chain:     {len(migrations)}")
    print(f"Migration files in chain: {[f.name for f in ordered_migration_chain()]}")

    if only_in_models:
        print(f"MISMATCH -- in models but not created by any migration: {sorted(only_in_models)}")
    if only_in_migrations:
        print(f"MISMATCH -- created by a migration but not in models: {sorted(only_in_migrations)}")

    if only_in_models or only_in_migrations:
        return 1

    print(f"PASSED -- the full migration chain creates exactly the {len(models)} tables the models declare, no drift.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
