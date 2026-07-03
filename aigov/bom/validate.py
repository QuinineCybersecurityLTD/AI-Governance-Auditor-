"""Real validation, not assertion.

CycloneDX: the library's JsonStrictValidator with the bundled official 1.7
schema. SPDX: (1) the official SPDX 3.0.1 JSON schema (vendored from
spdx.org/schema/3.0.1), and (2) a round-trip through the official
JSONLDDeserializer, which re-checks the SHACL-derived type model and link
integrity.
"""

from __future__ import annotations

import io
import json
from pathlib import Path

import jsonschema
from cyclonedx.schema import SchemaVersion
from cyclonedx.validation.json import JsonStrictValidator
from spdx_python_model import v3_0_1 as spdx

_SPDX_SCHEMA_PATH = Path(__file__).parent / "schemas" / "spdx-3.0.1-schema.json"


def validate_cdx(bom: dict) -> list[str]:
    """Returns a list of validation errors; empty list == valid."""
    error = JsonStrictValidator(SchemaVersion.V1_7).validate_str(json.dumps(bom))
    return [str(error)] if error else []


def validate_spdx(payload: dict) -> list[str]:
    """Returns a list of validation errors; empty list == valid."""
    errors: list[str] = []

    schema = json.loads(_SPDX_SCHEMA_PATH.read_text(encoding="utf-8"))
    validator = jsonschema.Draft202012Validator(schema)
    for err in validator.iter_errors(payload):
        errors.append(f"jsonschema: {err.message[:200]} (at {'/'.join(map(str, err.absolute_path))})")
        if len(errors) >= 10:
            break

    try:
        objset = spdx.SHACLObjectSet()
        spdx.JSONLDDeserializer().read(
            io.BytesIO(json.dumps(payload).encode("utf-8")), objset
        )
        n = sum(1 for _ in objset.foreach())
        if n == 0:
            errors.append("round-trip: deserializer produced no objects")
    except Exception as e:  # deserializer raises on model violations
        errors.append(f"round-trip: {e}")

    return errors
