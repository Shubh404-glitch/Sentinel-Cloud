"""Stage 2 static check: security invariants for the authentication
subsystem (Section 15). Stdlib-only (ast + text scan), same sandbox
constraint as the other scripts/check_*.py files -- this runs without
passlib/python-jose installed.

Checks:
  1. No weak/inappropriate hash functions (md5, sha1) anywhere under
     security/ or services/ -- password and token hashing must go
     through the two sanctioned primitives (bcrypt via passlib for
     passwords, sha256 via hashlib for opaque tokens), never a
     hand-rolled or weak alternative.
  2. security/jwt_tokens.py's allowed-algorithm set never includes
     "none" or is empty (the "alg=none" JWT vulnerability class).
  3. No domain model in domain/ persists a raw/plaintext secret
     column (e.g. a `raw_key`, `plaintext_token`, `password` column
     instead of `hashed_*`) -- every credential-shaped column name
     found must be prefixed `hashed_`.
  4. Every route in api/routes/auth.py that returns a TokenPairResponse
     is reachable only after either explicit credential verification
     (login, refresh) -- i.e. login/refresh must reference AuthService,
     not construct a token response some other way.
"""
from __future__ import annotations

import ast
import pathlib
import re
import sys

BACKEND_DIR = pathlib.Path(__file__).resolve().parents[1]
SRC_DIR = BACKEND_DIR / "src" / "sentinelscan_cloud"
SECURITY_DIR = SRC_DIR / "security"
SERVICES_DIR = SRC_DIR / "services"
DOMAIN_DIR = SRC_DIR / "domain"
ROUTES_AUTH_FILE = SRC_DIR / "api" / "routes" / "auth.py"
JWT_TOKENS_FILE = SECURITY_DIR / "jwt_tokens.py"

WEAK_HASH_PATTERN = re.compile(r"\b(md5|sha1)\s*\(", re.IGNORECASE)


def check_no_weak_hashes() -> list[str]:
    errors = []
    for d in (SECURITY_DIR, SERVICES_DIR):
        for f in d.glob("*.py"):
            text = f.read_text()
            for match in WEAK_HASH_PATTERN.finditer(text):
                line_no = text[: match.start()].count("\n") + 1
                errors.append(f"{f.relative_to(BACKEND_DIR)}:{line_no}: forbidden weak hash function {match.group(1)!r} used")
    return errors


def check_jwt_algorithm_allowlist() -> list[str]:
    errors = []
    text = JWT_TOKENS_FILE.read_text()
    tree = ast.parse(text, filename=str(JWT_TOKENS_FILE))

    allowlist_values: set[str] | None = None
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
            if isinstance(target, ast.Name) and target.id == "_ALLOWED_ALGORITHMS":
                if isinstance(node.value, ast.Set):
                    allowlist_values = set()
                    for elt in node.value.elts:
                        if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                            allowlist_values.add(elt.value)

    if allowlist_values is None:
        errors.append(f"{JWT_TOKENS_FILE.relative_to(BACKEND_DIR)}: could not find a literal _ALLOWED_ALGORITHMS set")
    elif not allowlist_values:
        errors.append(f"{JWT_TOKENS_FILE.relative_to(BACKEND_DIR)}: _ALLOWED_ALGORITHMS is empty")
    elif "none" in {v.lower() for v in allowlist_values}:
        errors.append(f"{JWT_TOKENS_FILE.relative_to(BACKEND_DIR)}: _ALLOWED_ALGORITHMS must not include 'none'")

    return errors


def check_no_plaintext_credential_columns() -> list[str]:
    errors = []
    for f in DOMAIN_DIR.glob("*.py"):
        if f.name in ("__init__.py", "base.py", "enums.py"):
            continue
        tree = ast.parse(f.read_text(), filename=str(f))
        for node in ast.walk(tree):
            if not (isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)):
                continue
            attr_name = node.target.id

            # Only actual database columns are in scope -- relationship()
            # attributes (e.g. Organization.api_keys, a list of related
            # rows) are not columns and can't store a plaintext secret.
            if not (isinstance(node.value, ast.Call) and _call_name(node.value) == "mapped_column"):
                continue

            tokens = set(attr_name.lower().split("_"))
            is_storage_reference = "storage" in tokens or "blob" in tokens
            is_foreign_key_id = attr_name.lower().endswith("_id")
            looks_credential_shaped = (
                not is_foreign_key_id
                and (
                    "password" in tokens
                    or "secret" in tokens
                    or "token" in tokens
                    or ("key" in tokens and not is_storage_reference)
                )
            )
            if not looks_credential_shaped:
                continue

            # key_prefix is a deliberate, documented exception: it stores
            # only the first few characters of an API key for UI display,
            # never a usable credential.
            if attr_name == "key_prefix":
                continue

            if not attr_name.lower().startswith("hashed_"):
                errors.append(
                    f"{f.relative_to(BACKEND_DIR)}: column {attr_name!r} looks credential-shaped "
                    f"but is not prefixed 'hashed_' -- verify it does not store a raw secret"
                )
    return errors


def _call_name(call: ast.Call) -> str | None:
    if isinstance(call.func, ast.Name):
        return call.func.id
    if isinstance(call.func, ast.Attribute):
        return call.func.attr
    return None


def check_login_and_refresh_use_auth_service() -> list[str]:
    errors = []
    text = ROUTES_AUTH_FILE.read_text()
    tree = ast.parse(text, filename=str(ROUTES_AUTH_FILE))

    imports_auth_service = any(
        isinstance(node, ast.ImportFrom) and node.module and node.module.endswith("services.auth_service")
        for node in ast.walk(tree)
    )
    if not imports_auth_service:
        errors.append(f"{ROUTES_AUTH_FILE.relative_to(BACKEND_DIR)}: does not import AuthService from services.auth_service")
        return errors

    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef) and node.name in ("login", "refresh"):
            calls_auth_service = any(
                isinstance(n, ast.Attribute) and n.attr in ("authenticate", "issue_token_pair", "refresh")
                for n in ast.walk(node)
            )
            if not calls_auth_service:
                errors.append(f"{ROUTES_AUTH_FILE.relative_to(BACKEND_DIR)}: route {node.name!r} does not call into AuthService")

    return errors


def main() -> int:
    errors: list[str] = []
    errors += check_no_weak_hashes()
    errors += check_jwt_algorithm_allowlist()
    errors += check_no_plaintext_credential_columns()
    errors += check_login_and_refresh_use_auth_service()

    print("Checked: weak hash functions (md5/sha1) in security/ and services/")
    print("Checked: JWT algorithm allowlist excludes 'none' and is non-empty")
    print("Checked: domain models have no unhashed credential-shaped columns")
    print("Checked: login/refresh routes delegate to AuthService")
    print()

    if errors:
        print(f"FAILED -- {len(errors)} issue(s) found:")
        for e in errors:
            print(f"  \u2717 {e}")
        return 1

    print("PASSED -- all Stage 2 authentication security invariants hold.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
