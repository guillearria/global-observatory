"""Schema loading + validation, including the Python-only checks the JSON Schema can't express.

The schema file is deliberately free of pattern/min/max keywords so it can double as a Claude
structured-output format. The slug pattern and numeric ranges are enforced here instead.
"""

from __future__ import annotations

import functools
import json

import jsonschema

from . import config, models


class ValidationError(Exception):
    """Raised when a record fails schema validation or a Python-side invariant."""


@functools.lru_cache(maxsize=1)
def load_schema() -> dict:
    return json.loads(config.SCHEMA_PATH.read_text(encoding="utf-8"))


@functools.lru_cache(maxsize=1)
def _validator() -> jsonschema.Draft202012Validator:
    schema = load_schema()
    jsonschema.Draft202012Validator.check_schema(schema)
    return jsonschema.Draft202012Validator(schema)


def validate(record: dict) -> None:
    """Validate a record. Raises ValidationError with all problems joined."""
    msgs = [
        f"{list(e.absolute_path)}: {e.message}"
        for e in sorted(_validator().iter_errors(record), key=lambda e: list(e.absolute_path))
    ]

    slug = record.get("id")
    if isinstance(slug, str) and not models.slug_ok(slug):
        msgs.append(f"id: {slug!r} does not match ^[a-z0-9-]+$")

    sk = record.get("sort_keys") or {}
    sr = sk.get("severity_rank")
    if isinstance(sr, int) and not 1 <= sr <= 4:
        msgs.append(f"sort_keys.severity_rank: {sr} out of range 1-4")
    pr = sk.get("probability_rank")
    if isinstance(pr, int) and not 1 <= pr <= 5:
        msgs.append(f"sort_keys.probability_rank: {pr} out of range 1-5")

    if msgs:
        raise ValidationError("; ".join(msgs))
