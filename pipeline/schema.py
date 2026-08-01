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


_SCHEMA_PATHS = {
    "threat": lambda: config.SCHEMA_PATH,
    "event": lambda: config.EVENT_SCHEMA_PATH,
    "historical": lambda: config.HISTORICAL_SCHEMA_PATH,
    # Not a record kind — the allowlist is a single document, validated by
    # validate_source_allowlist() rather than by validate(), which assumes a record
    # (slug + range checks). It shares the loader so schemas load one way.
    "source-allowlist": lambda: config.SOURCE_ALLOWLIST_SCHEMA_PATH,
}


@functools.cache
def load_schema(kind: str = "threat") -> dict:
    return json.loads(_SCHEMA_PATHS[kind]().read_text(encoding="utf-8"))


@functools.cache
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
    loc = (record.get("event") or {}).get("location") or {}
    lat, lon = loc.get("lat"), loc.get("lon")
    if isinstance(lat, (int, float)) and not -90 <= lat <= 90:
        msgs.append(f"event.location.lat: {lat} out of range -90..90")
    if isinstance(lon, (int, float)) and not -180 <= lon <= 180:
        msgs.append(f"event.location.lon: {lon} out of range -180..180")
    return msgs


def _historical_range_checks(record: dict) -> list[str]:
    msgs = []
    sk = record.get("sort_keys") or {}
    cr = sk.get("chronology_rank")
    cr_max = config.HISTORICAL_YEAR_MAX + config.HISTORICAL_YEAR_OFFSET
    if isinstance(cr, int) and not 1 <= cr <= cr_max:
        msgs.append(
            f"sort_keys.chronology_rank: {cr} out of range 1-{cr_max} "
            f"(years {config.HISTORICAL_YEAR_MIN}..{config.HISTORICAL_YEAR_MAX})"
        )
    ir = sk.get("impact_rank")
    if isinstance(ir, int) and not 1 <= ir <= 5:
        msgs.append(f"sort_keys.impact_rank: {ir} out of range 1-5")
    hist = record.get("historical") or {}
    ys, ye = hist.get("year_start"), hist.get("year_end")
    if isinstance(ys, int) and isinstance(ye, int) and ye < ys:
        msgs.append(f"historical.year_end: {ye} precedes year_start {ys}")
    impact = hist.get("impact") or {}
    lo, hi = impact.get("deaths_low"), impact.get("deaths_high")
    if isinstance(lo, (int, float)) and isinstance(hi, (int, float)) and lo > hi:
        msgs.append(f"historical.impact.deaths_low: {lo} exceeds deaths_high {hi}")
    return msgs


_RANGE_CHECKS = {
    "threat": _threat_range_checks,
    "event": _event_range_checks,
    "historical": _historical_range_checks,
}


def validate_source_allowlist(doc: dict) -> list[str]:
    """Validate the source allowlist document. Returns a list of problems (empty = valid).

    Refresh runs can extend this file and it auto-publishes with no reviewer, so the checks
    here are the only thing standing between a careless addition and a domain being treated
    as authoritative. Duplicate domains are rejected in Python because the shape is a list
    (chosen so entries can carry a justification), and JSON Schema cannot express uniqueness
    on one property.
    """
    msgs = [
        f"{list(e.absolute_path)}: {e.message}"
        for e in sorted(
            _validator("source-allowlist").iter_errors(doc), key=lambda e: list(e.absolute_path)
        )
    ]
    seen: set[str] = set()
    for entry in doc.get("sources", []):
        domain = entry.get("domain") if isinstance(entry, dict) else None
        if not isinstance(domain, str):
            continue
        if domain in seen:
            msgs.append(f"domain {domain!r} is listed more than once")
        seen.add(domain)
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

    msgs += _RANGE_CHECKS[kind](record)

    if msgs:
        raise ValidationError("; ".join(msgs))
