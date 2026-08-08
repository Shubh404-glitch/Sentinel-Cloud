"""
Schema validation against the approved Report Export Schema v1
(schemas/report_export/v1/), per Section 11 step 3-4.

This intentionally has ZERO third-party dependencies (no `jsonschema`
package): this sandbox has no network access to install one, and more
importantly, avoiding an extra dependency for a deliberately small,
fully-understood subset of JSON Schema (2020-12) keeps the one thing
that inspects every byte of untrusted input as simple and auditable as
possible (Section 15). This is the same validation logic as the
schema package's own design-time self-check
(schemas/report_export/v1's sibling check script), promoted to
production code and wired to actually reject invalid ingestion
payloads instead of just proving the examples pass at design time.

Supports exactly what schemas/report_export/v1/*.schema.json use:
type, required, properties, additionalProperties, items, minItems,
maxItems, minLength, maxLength, pattern, enum, const, allOf, $ref
(internal and cross-file), $defs. `format` is accepted but not
semantically checked (see the schema README).
"""
from __future__ import annotations

import json
import pathlib
import re
from functools import lru_cache
from typing import Any

from sentinelscan_cloud.ingestion.errors import SchemaValidationError, UnsupportedSchemaVersionError

SCHEMA_DIR = pathlib.Path(__file__).resolve().parents[4] / "schemas" / "report_export"
# .../backend/src/sentinelscan_cloud/ingestion/schema_validation/validator.py
#   parents[0]=schema_validation parents[1]=ingestion parents[2]=sentinelscan_cloud
#   parents[3]=src parents[4]=backend -> backend/schemas/report_export
SUPPORTED_MAJOR_VERSION = 1

_EDITION_TO_SCHEMA_FILE = {
    "discover": "discover.schema.json",
    "operate": "operate.schema.json",
}


@lru_cache
def _schema_dir_for_version(major_version: int) -> pathlib.Path:
    return SCHEMA_DIR / f"v{major_version}"


@lru_cache
def _load_schema(schema_dir: pathlib.Path, filename: str) -> dict:
    path = schema_dir / filename
    if not path.exists():
        raise UnsupportedSchemaVersionError(f"no schema file {filename!r} found under {schema_dir}")
    return json.loads(path.read_text())


def _resolve_ref(ref: str, current_file: str, schema_dir: pathlib.Path) -> tuple[dict, str]:
    if "#" not in ref:
        raise SchemaValidationError(f"unsupported $ref (no '#'): {ref}")
    file_part, pointer = ref.split("#", 1)
    target_file = file_part if file_part else current_file
    doc = _load_schema(schema_dir, target_file)

    node: Any = doc
    if pointer:
        for part in pointer.strip("/").split("/"):
            part = part.replace("~1", "/").replace("~0", "~")
            if not isinstance(node, dict) or part not in node:
                raise SchemaValidationError(f"$ref pointer {pointer!r} not found in {target_file}")
            node = node[part]
    return node, target_file


def _type_matches(value: Any, expected: str | list[str]) -> bool:
    types = expected if isinstance(expected, list) else [expected]
    for t in types:
        if t == "object" and isinstance(value, dict):
            return True
        if t == "array" and isinstance(value, list):
            return True
        if t == "string" and isinstance(value, str):
            return True
        if t == "integer" and isinstance(value, int) and not isinstance(value, bool):
            return True
        if t == "number" and isinstance(value, (int, float)) and not isinstance(value, bool):
            return True
        if t == "boolean" and isinstance(value, bool):
            return True
        if t == "null" and value is None:
            return True
    return False


def _validate(instance: Any, schema: dict, current_file: str, schema_dir: pathlib.Path, path: str = "$") -> None:
    if "$ref" in schema:
        resolved, resolved_file = _resolve_ref(schema["$ref"], current_file, schema_dir)
        _validate(instance, resolved, resolved_file, schema_dir, path)
        return

    if "allOf" in schema:
        for sub in schema["allOf"]:
            _validate(instance, sub, current_file, schema_dir, path)

    if "const" in schema:
        if instance != schema["const"]:
            raise SchemaValidationError(f"expected const {schema['const']!r}, got {instance!r}", path=path)

    if "enum" in schema:
        if instance not in schema["enum"]:
            raise SchemaValidationError(f"{instance!r} not in enum {schema['enum']!r}", path=path)

    if "type" in schema:
        if not _type_matches(instance, schema["type"]):
            raise SchemaValidationError(
                f"expected type {schema['type']!r}, got {type(instance).__name__} ({instance!r})", path=path
            )

    if isinstance(instance, str):
        if "minLength" in schema and len(instance) < schema["minLength"]:
            raise SchemaValidationError(f"string shorter than minLength {schema['minLength']}", path=path)
        if "maxLength" in schema and len(instance) > schema["maxLength"]:
            raise SchemaValidationError(f"string longer than maxLength {schema['maxLength']}", path=path)
        if "pattern" in schema and not re.match(schema["pattern"], instance):
            raise SchemaValidationError(f"{instance!r} does not match pattern {schema['pattern']!r}", path=path)

    if isinstance(instance, list):
        if "minItems" in schema and len(instance) < schema["minItems"]:
            raise SchemaValidationError(f"array shorter than minItems {schema['minItems']}", path=path)
        if "maxItems" in schema and len(instance) > schema["maxItems"]:
            raise SchemaValidationError(f"array longer than maxItems {schema['maxItems']}", path=path)
        if "items" in schema:
            for i, item in enumerate(instance):
                _validate(item, schema["items"], current_file, schema_dir, f"{path}[{i}]")

    if isinstance(instance, dict):
        properties = schema.get("properties", {})
        for required_key in schema.get("required", []):
            if required_key not in instance:
                raise SchemaValidationError(f"missing required property {required_key!r}", path=path)
        for key, value in instance.items():
            if key in properties:
                _validate(value, properties[key], current_file, schema_dir, f"{path}.{key}")
            elif schema.get("additionalProperties") is False:
                raise SchemaValidationError(f"unexpected additional property {key!r}", path=path)


def parse_schema_version(schema_version: str) -> tuple[int, int]:
    match = re.match(r"^(\d+)\.(\d+)$", schema_version or "")
    if not match:
        raise UnsupportedSchemaVersionError(f"malformed schema_version {schema_version!r}, expected MAJOR.MINOR")
    return int(match.group(1)), int(match.group(2))


def select_schema_file(source_edition: str, schema_version: str) -> tuple[pathlib.Path, str]:
    """Section 11 step 4: choose which schema file to validate against
    from (source_edition, schema_version), per the schema README's
    versioning contract (decision #3): a MINOR version always validates
    against the same MAJOR schema file; an unrecognized MAJOR version
    is rejected outright, never coerced to the nearest known one."""
    if source_edition not in _EDITION_TO_SCHEMA_FILE:
        raise UnsupportedSchemaVersionError(f"unknown source_edition {source_edition!r}")

    major, _minor = parse_schema_version(schema_version)
    if major != SUPPORTED_MAJOR_VERSION:
        raise UnsupportedSchemaVersionError(
            f"unsupported schema_version {schema_version!r} (only major version {SUPPORTED_MAJOR_VERSION} is supported)"
        )

    schema_dir = _schema_dir_for_version(major)
    filename = _EDITION_TO_SCHEMA_FILE[source_edition]
    if not (schema_dir / filename).exists():
        raise UnsupportedSchemaVersionError(f"no schema found for {source_edition!r} at v{major}")
    return schema_dir, filename


def validate_report_payload(payload: dict) -> None:
    """Validate a parsed JSON payload against the schema selected by its
    own (source_edition, schema_version) fields. Raises
    UnsupportedSchemaVersionError or SchemaValidationError; returns
    None on success. Does not mutate or coerce the payload in any way
    (Section 15: rejected outright, never silently truncated/coerced)."""
    if not isinstance(payload, dict):
        raise SchemaValidationError(f"top-level payload must be a JSON object, got {type(payload).__name__}")

    source_edition = payload.get("source_edition")
    schema_version = payload.get("schema_version")
    schema_dir, filename = select_schema_file(source_edition, schema_version)

    schema = _load_schema(schema_dir, filename)
    _validate(payload, schema, filename, schema_dir)
