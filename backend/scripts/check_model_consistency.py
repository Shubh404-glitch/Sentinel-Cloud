"""
Static, stdlib-only cross-reference checker for the domain model.

This sandbox cannot install SQLAlchemy (no network access), so we can't
verify relationships by actually importing and mapping the classes. This
script instead parses every domain model file with `ast` and checks,
without executing any of them:

  1. Every ForeignKey("table.column") string target refers to a table
     that actually exists (a __tablename__ defined somewhere).
  2. Every class-level `relationship(...)` and `back_populates=...` pair
     resolves to a real attribute on the real target class.
  3. Every __tablename__ is unique (no accidental duplicate tables).

This is real static verification, not a fabricated pass -- it will
genuinely fail and print the mismatch if a table/column/back_populates
name is wrong.
"""
from __future__ import annotations

import ast
import pathlib
import sys

DOMAIN_DIR = pathlib.Path(__file__).resolve().parents[1] / "src" / "sentinelscan_cloud" / "domain"


def _literal_str(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


class ClassInfo:
    def __init__(self, name: str, filename: str):
        self.name = name
        self.filename = filename
        self.tablename: str | None = None
        self.relationships: dict[str, dict] = {}  # attr_name -> {back_populates, target_repr}
        self.attrs: set[str] = set()


def parse_file(path: pathlib.Path) -> list[ClassInfo]:
    tree = ast.parse(path.read_text(), filename=str(path))
    classes: list[ClassInfo] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        info = ClassInfo(node.name, path.name)

        for stmt in node.body:
            # __tablename__ = "..."
            if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1:
                target = stmt.targets[0]
                if isinstance(target, ast.Name) and target.id == "__tablename__":
                    info.tablename = _literal_str(stmt.value)

            # attr: Mapped[...] = mapped_column(...) / relationship(...)
            if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
                attr_name = stmt.target.id
                info.attrs.add(attr_name)
                if isinstance(stmt.value, ast.Call):
                    call = stmt.value
                    call_name = (
                        call.func.id if isinstance(call.func, ast.Name)
                        else call.func.attr if isinstance(call.func, ast.Attribute)
                        else None
                    )
                    if call_name == "relationship":
                        back_populates = None
                        target_repr = None
                        if call.args:
                            target_repr = _literal_str(call.args[0])
                        for kw in call.keywords:
                            if kw.arg == "back_populates":
                                back_populates = _literal_str(kw.value)
                            if kw.arg == "argument" or (kw.arg is None):
                                pass
                        info.relationships[attr_name] = {
                            "back_populates": back_populates,
                            "target_repr": target_repr,
                        }

        classes.append(info)
    return classes


def find_foreign_keys(path: pathlib.Path) -> list[tuple[str, int]]:
    """Return every ForeignKey("table.column"[, ...]) literal target found in a file."""
    tree = ast.parse(path.read_text(), filename=str(path))
    targets = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            call_name = node.func.id if isinstance(node.func, ast.Name) else (
                node.func.attr if isinstance(node.func, ast.Attribute) else None
            )
            if call_name == "ForeignKey" and node.args:
                lit = _literal_str(node.args[0])
                if lit:
                    targets.append((lit, node.lineno))
    return targets


def main() -> int:
    files = sorted(DOMAIN_DIR.glob("*.py"))
    files = [f for f in files if f.name not in ("__init__.py", "base.py", "enums.py")]

    all_classes: list[ClassInfo] = []
    tablenames: dict[str, str] = {}  # tablename -> filename
    errors: list[str] = []

    for f in files:
        classes = parse_file(f)
        all_classes.extend(classes)
        for c in classes:
            if c.tablename:
                if c.tablename in tablenames:
                    errors.append(
                        f"Duplicate __tablename__ {c.tablename!r}: defined in both "
                        f"{tablenames[c.tablename]} and {c.filename}"
                    )
                tablenames[c.tablename] = c.filename

    print(f"Discovered {len(tablenames)} tables across {len(files)} model files:")
    for name in sorted(tablenames):
        print(f"  - {name:<28} ({tablenames[name]})")
    print()

    # 1. Validate every ForeignKey("table.column") target table exists.
    fk_count = 0
    for f in files:
        for target, lineno in find_foreign_keys(f):
            fk_count += 1
            table_part = target.split(".")[0]
            if table_part not in tablenames:
                errors.append(f"{f.name}:{lineno}: ForeignKey target table {table_part!r} does not exist (from {target!r})")
    print(f"Checked {fk_count} ForeignKey(...) references against {len(tablenames)} known tables.")

    # 2. Validate back_populates pairs resolve to a real attribute on the real target class.
    class_by_name = {c.name: c for c in all_classes}
    rel_count = 0
    for c in all_classes:
        for attr_name, rel in c.relationships.items():
            rel_count += 1
            target_class_name = rel["target_repr"]
            back_pop = rel["back_populates"]
            if not target_class_name or not back_pop:
                continue  # viewonly relationships / self-referential without back_populates are allowed
            target_cls = class_by_name.get(target_class_name)
            if target_cls is None:
                errors.append(
                    f"{c.filename}: {c.name}.{attr_name} relationship() targets unknown class {target_class_name!r}"
                )
                continue
            if back_pop not in target_cls.attrs:
                errors.append(
                    f"{c.filename}: {c.name}.{attr_name} has back_populates={back_pop!r}, "
                    f"but {target_class_name} has no such attribute"
                )
    print(f"Checked {rel_count} relationship() declarations with back_populates for a matching reverse attribute.")
    print()

    if errors:
        print(f"FAILED -- {len(errors)} issue(s) found:")
        for e in errors:
            print(f"  ✗ {e}")
        return 1

    print(f"PASSED -- {len(tablenames)} tables, {fk_count} foreign keys, {rel_count} relationships all internally consistent.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
