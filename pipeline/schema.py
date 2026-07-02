"""Schema loading + validation, including the Python-only checks the JSON Schema can't express.

The schema files carry no pattern/min/max keywords (a historical constraint kept for simplicity),
so the slug pattern and numeric ranges are enforced here in Python instead.
"""

from __future__ import annotations

import functools
import json

import jsonschema

from . import config, models


class ValidationError(Exception):
    """Raised when a record fails schema validation or a Python-side invariant."""


_SCHEMA_PATHS = {"threat": lambda: config.SCHEMA_PATH, "event": lambda: config.EVENT_SCHEMA_PATH}


@functools.lru_cache(maxsize=None)
def load_schema(kind: str = "threat") -> dict:
    return json.loads(_SCHEMA_PATHS[kind]().read_text(encoding="utf-8"))


@functools.lru_cache(maxsize=None)
def _validator(kind: str = "threat") -> jsonschema.Draft202012Validator:
    schema = load_schema(kind)
    jsonschema.Draft202012Validator.check_schema(schema)
    return jsonschema.Draft202012Validator(schema)


def _threat_range_checks(record: dict) -> list[str]:
    msgs = []
    sk = record.get("sort_keys") or {}
    sr = sk.get("severity_rank")
    if isinstance(sr, int) and not 1 <= sr <= 4:
        msgs.append(f"sort_keys.severity_rank: {sr} out of range 1-4")
    pr = sk.get("probability_rank")
    if isinstance(pr, int) and not 1 <= pr <= 5:
        msgs.append(f"sort_keys.probability_rank: {pr} out of range 1-5")
    return msgs


def _event_range_checks(record: dict) -> list[str]:
    msgs = []
    sk = record.get("sort_keys") or {}
    rr = sk.get("recency_rank")
    if isinstance(rr, int) and rr <= 0:
        msgs.append(f"sort_keys.recency_rank: {rr} must be a positive day-ordinal")
    ir = sk.get("impact_rank")
    if isinstance(ir, int) and not 1 <= ir <= 4:
        msgs.append(f"sort_keys.impact_rank: {ir} out of range 1-4")
    return msgs


def validate(record: dict, kind: str = "threat") -> None:
    """Validate a record against its kind's schema. Raises ValidationError with all problems joined."""
    msgs = [
        f"{list(e.absolute_path)}: {e.message}"
        for e in sorted(_validator(kind).iter_errors(record), key=lambda e: list(e.absolute_path))
    ]

    slug = record.get("id")
    if isinstance(slug, str) and not models.slug_ok(slug):
        msgs.append(f"id: {slug!r} does not match ^[a-z0-9-]+$")

    msgs += _event_range_checks(record) if kind == "event" else _threat_range_checks(record)

    if msgs:
        raise ValidationError("; ".join(msgs))
