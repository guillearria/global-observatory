"""Schema loading + validation, including the Python-only checks the JSON Schema can't express.

The schema files carry no pattern/min/max keywords (a historical constraint kept for simplicity),
so the slug pattern and numeric ranges are enforced here in Python instead.
"""

from __future__ import annotations

import functools
import json
from datetime import date

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


# --- Prose discipline --------------------------------------------------------
# description and the kind summary are current-state editorial prose, rewritten in
# place on refresh. These checks refuse the two ways past refreshes degraded them:
# process narration ("Re-checked 8 August …") and unbounded append growth. Scope is
# prose fields only — claims[].text is exempt (legacy claims kept verbatim carry
# process prefixes, and old claim text is never restyled).

def _prose_fields(record: dict, kind: str) -> list[tuple[str, str, int]]:
    """(path, text, max_chars) triples of the prose fields this kind must keep clean."""
    fields = [("description", record.get("description"), config.DESCRIPTION_MAX_CHARS)]
    if kind == "threat":
        summary = (record.get("assessment") or {}).get("summary")
        fields.append(("assessment.summary", summary, config.SUMMARY_MAX_CHARS))
    elif kind == "historical":
        summary = ((record.get("historical") or {}).get("impact") or {}).get("summary")
        fields.append(("historical.impact.summary", summary, config.SUMMARY_MAX_CHARS))
    else:
        ev = record.get("event") or {}
        fields.append(
            ("event.impact.summary", (ev.get("impact") or {}).get("summary"),
             config.SUMMARY_MAX_CHARS))
        fields.append(
            ("event.location.region", (ev.get("location") or {}).get("region"),
             config.EVENT_REGION_MAX_CHARS))
        for i, entry in enumerate(record.get("updates") or []):
            if isinstance(entry, dict):
                fields.append(
                    (f"updates[{i}].text", entry.get("text"),
                     config.EVENT_UPDATE_TEXT_MAX_CHARS))
    # Non-string values are the JSON Schema's problem, not ours.
    return [(path, text, cap) for path, text, cap in fields if isinstance(text, str)]


def _updates_checks(record: dict) -> list[str]:
    """Shape checks for the event `updates[]` development log (events only)."""
    msgs = []
    updates = record.get("updates")
    if updates is None:
        return msgs
    if not isinstance(updates, list):
        return msgs  # the JSON Schema reports the type mismatch
    if len(updates) > config.EVENT_UPDATES_MAX_ENTRIES:
        msgs.append(
            f"updates: {len(updates)} entries exceeds the cap of "
            f"{config.EVENT_UPDATES_MAX_ENTRIES} — condense older entries"
        )
    dates = []
    for i, entry in enumerate(updates):
        if not isinstance(entry, dict):
            continue  # schema reports it
        raw = entry.get("date")
        if not isinstance(raw, str):
            continue  # schema reports it
        try:
            dates.append(date.fromisoformat(raw))
        except ValueError:
            msgs.append(f"updates[{i}].date: {raw!r} is not an ISO date (YYYY-MM-DD)")
            dates.append(None)
    known = [d for d in dates if d is not None]
    if known != sorted(known, reverse=True):
        msgs.append("updates: entries must be sorted newest-first by date")
    return msgs


def _prose_checks(record: dict, kind: str) -> list[str]:
    """Length caps + forbidden process-language substrings on prose fields."""
    forbidden = (
        config.EVENT_PROSE_FORBIDDEN_PHRASES if kind == "event"
        else config.PROSE_FORBIDDEN_PHRASES
    )
    msgs = []
    for path, text, cap in _prose_fields(record, kind):
        if len(text) > cap:
            msgs.append(
                f"{path}: {len(text)} chars exceeds the {cap}-char cap — keep it "
                "current-state prose; dated developments belong in updates[]"
            )
        lowered = text.lower()
        for phrase in forbidden:
            if phrase in lowered:
                msgs.append(
                    f"{path}: contains process language ({phrase!r}) — rewrite as "
                    "current-state prose; re-verification notes belong in updates[] "
                    "or in claims' retrieved_date, never in prose"
                )
    if kind == "event":
        msgs += _updates_checks(record)
    return msgs


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
    msgs += _prose_checks(record, kind)

    if msgs:
        raise ValidationError("; ".join(msgs))
