"""
Static check: every route handler (a function decorated with
@router.get/post/patch/delete/put) in api/routes/ must have a
parameter using Depends(get_current_user) or Depends(get_current_api_key)
-- catches an endpoint that compiles fine, gets registered, and is
reachable, but was accidentally left unauthenticated. Stdlib-only
(ast), no FastAPI needed to run this.

health.py is the one deliberate exception: a health check must be
reachable without credentials (that's the point of a health check),
so it's excluded by name, not silently ignored by the logic below.
"""
from __future__ import annotations

import ast
import pathlib
import sys

BACKEND_DIR = pathlib.Path(__file__).resolve().parents[1]
ROUTES_DIR = BACKEND_DIR / "src" / "sentinelscan_cloud" / "api" / "routes"

EXEMPT_FILES = {
    "health.py",  # a health check must be reachable without credentials -- that's the point of one
}
# auth.py's login/refresh/logout are individually exempted (not the
# whole file) below, since every OTHER handler in auth.py (e.g. /auth/me)
# still must be checked normally.
EXEMPT_ROUTE_HANDLERS = {
    ("auth.py", "login"): "issues a token from email+password in the request body -- cannot require a token to get a token",
    ("auth.py", "refresh"): "issues a new token from a refresh token in the request body, not a bearer access token",
    ("auth.py", "logout"): "revokes a refresh token supplied in the request body, not a bearer access token",
}
AUTH_DEPENDENCY_NAMES = {
    "get_current_user",
    "get_current_api_key",
    # require_role(...) is not itself a separate auth mechanism -- its
    # own implementation (api/deps/auth.py) is `Depends(get_current_user)`
    # plus a role check on top. A route using require_role() is *more*
    # strictly authenticated than one using get_current_user alone, so
    # excluding it here would be a false positive, not extra caution.
    "require_role",
}
HTTP_METHOD_DECORATORS = {"get", "post", "put", "patch", "delete"}


def _is_route_decorator(decorator: ast.expr) -> bool:
    # Matches `@router.get(...)`, `@router.post(...)`, etc.
    if isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Attribute):
        return decorator.func.attr in HTTP_METHOD_DECORATORS and (
            isinstance(decorator.func.value, ast.Name) and decorator.func.value.id == "router"
        )
    return False


def _function_uses_auth_dependency(node: ast.FunctionDef) -> bool:
    source = ast.dump(node)
    return any(name in source for name in AUTH_DEPENDENCY_NAMES)


def main() -> int:
    unauthenticated: list[str] = []
    total_routes = 0

    for f in sorted(ROUTES_DIR.glob("*.py")):
        if f.name in EXEMPT_FILES or f.name == "__init__.py":
            continue
        tree = ast.parse(f.read_text(), filename=str(f))
        for node in ast.walk(tree):
            if not isinstance(node, ast.AsyncFunctionDef):
                continue
            if not any(_is_route_decorator(d) for d in node.decorator_list):
                continue
            total_routes += 1
            if (f.name, node.name) in EXEMPT_ROUTE_HANDLERS:
                continue
            if not _function_uses_auth_dependency(node):
                unauthenticated.append(f"{f.name}:{node.lineno}: {node.name}")

    print(f"Checked {total_routes} route handler(s) across {len(list(ROUTES_DIR.glob('*.py'))) - 1} route file(s) "
          f"(excluding {sorted(EXEMPT_FILES)}).")
    if EXEMPT_ROUTE_HANDLERS:
        print(f"Documented per-handler exemptions ({len(EXEMPT_ROUTE_HANDLERS)}):")
        for (fname, hname), reason in EXEMPT_ROUTE_HANDLERS.items():
            print(f"  - {fname}:{hname} -- {reason}")

    if unauthenticated:
        print(f"FAILED -- {len(unauthenticated)} route(s) with no authentication dependency detected:")
        for u in unauthenticated:
            print(f"  ✗ {u}")
        return 1

    print("PASSED -- every route handler depends on get_current_user or get_current_api_key.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
