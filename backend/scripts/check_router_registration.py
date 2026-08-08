"""
Static check: every `router = APIRouter(...)` defined in a file under
api/routes/ must have a matching `app.include_router(<module>.router)`
call in api/main.py. Stdlib-only (ast), no FastAPI needed to run this.

Catches exactly the kind of mistake made easy by manually maintaining
two lists in sync (the route modules, and the include_router calls) --
a new route file that compiles fine and even has real endpoints, but
was simply never wired into the app and is therefore completely
unreachable.
"""
from __future__ import annotations

import ast
import pathlib
import sys

BACKEND_DIR = pathlib.Path(__file__).resolve().parents[1]
ROUTES_DIR = BACKEND_DIR / "src" / "sentinelscan_cloud" / "api" / "routes"
MAIN_FILE = BACKEND_DIR / "src" / "sentinelscan_cloud" / "api" / "main.py"


def modules_defining_a_router() -> set[str]:
    modules = set()
    for f in ROUTES_DIR.glob("*.py"):
        if f.name == "__init__.py":
            continue
        tree = ast.parse(f.read_text(), filename=str(f))
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign) and len(node.targets) == 1:
                target = node.targets[0]
                if isinstance(target, ast.Name) and target.id == "router":
                    modules.add(f.stem)
    return modules


def modules_registered_in_main() -> set[str]:
    tree = ast.parse(MAIN_FILE.read_text(), filename=str(MAIN_FILE))
    registered = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            call_name = node.func.attr if isinstance(node.func, ast.Attribute) else None
            if call_name == "include_router" and node.args:
                arg = node.args[0]
                # Expect the shape `app.include_router(<module_name>.router)`
                if isinstance(arg, ast.Attribute) and arg.attr == "router" and isinstance(arg.value, ast.Name):
                    registered.add(arg.value.id)
    return registered


def main() -> int:
    defined = modules_defining_a_router()
    registered = modules_registered_in_main()

    unregistered = defined - registered
    print(f"Route modules defining a router: {len(defined)} -> {sorted(defined)}")
    print(f"Route modules registered in main.py: {len(registered)} -> {sorted(registered)}")

    if unregistered:
        print(f"FAILED -- {len(unregistered)} route module(s) define a router but are never registered: {sorted(unregistered)}")
        return 1

    print("PASSED -- every route module's router is registered in api/main.py.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
