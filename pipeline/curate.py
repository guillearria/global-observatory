"""Deterministic, no-API authoring of a single record (threat or event).

The $0 path for adding or updating a record: Claude Code (on a Max subscription) or a human drafts
the factual content, and `finalize` runs it through the deterministic trust machinery — the
allowlist quarantine gate decides verified-vs-quarantined, never the drafter's say-so.

A draft is a published record MINUS the fields computed here: `verification`, `sort_keys`,
`provenance`, `last_updated`, and `schema_version` (defaulted). It must already contain `id`, `name`,
`category`, `description`, `assessment` (threats) or `event` (events), and `claims` (each with a
real `source_url` + `retrieved_date`).
"""

from __future__ import annotations

from datetime import date

from . import config, models, schema, store
from .gate import apply_gate


# --- Mechanical normalization (deterministic; no factual changes) -----------
def _normalize(record: dict) -> dict:
    """Stable claim sort, whitespace strip, case-insensitive dedup, source-name normalization."""
    record["name"] = record.get("name", "").strip()
    record["description"] = record.get("description", "").strip()

    a = record.get("assessment", {})
    if isinstance(a.get("summary"), str):
        a["summary"] = a["summary"].strip()
    if isinstance(a.get("timeframe"), str):
        a["timeframe"] = a["timeframe"].strip()

    seen: set[str] = set()
    claims: list[dict] = []
    for c in sorted(record.get("claims", []), key=lambda c: c.get("id", "")):
        c["text"] = c.get("text", "").strip()
        key = c["text"].lower()
        if key in seen:
            continue  # dedup identical claims
        seen.add(key)
        ok, label = config.allowlisted(c.get("source_url", "") or "")
        c["source_name"] = label if (ok and label) else c.get("source_name", "").strip()
        claims.append(c)
    record["claims"] = claims
    return record


# --- Sort keys (deterministic ranking) ---------------------------------------
def compute_sort_keys(record: dict, kind: str = "threat") -> dict:
    if kind == "event":
        return _event_sort_keys(record)
    a = record.get("assessment", {})
    sr = config.SEVERITY_RANK.get(a.get("severity"), 1)
    pr = config.PROBABILITY_RANK.get(a.get("probability", {}).get("estimate"), 1)
    # Severity dominates; probability breaks ties.
    return {"severity_rank": sr, "probability_rank": pr, "composite": float(sr * 10 + pr)}


def _recency_rank(occurrence_date: str) -> int:
    """Ordinal day number of the occurrence date; larger = more recent.

    Uses date.toordinal so the rank is stable (independent of 'today') — a rebuild
    next month yields the same file, yet newer events always outrank older ones.
    """
    try:
        return date.fromisoformat((occurrence_date or "")[:10]).toordinal()
    except ValueError:
        return 0


def _impact_rank(impact: dict) -> int:
    """1-4 from casualty/displacement bands; the larger signal wins (see config)."""
    rank = 1
    deaths = impact.get("deaths")
    displaced = impact.get("displaced")
    for value, bands in ((deaths, config.EVENT_IMPACT_DEATHS),
                         (displaced, config.EVENT_IMPACT_DISPLACED)):
        if isinstance(value, (int, float)):
            for threshold, r in bands:
                if value >= threshold:
                    rank = max(rank, r)
                    break
    return rank


def _event_sort_keys(record: dict) -> dict:
    ev = record.get("event", {})
    recency = _recency_rank(ev.get("occurrence_date", ""))
    impact = _impact_rank(ev.get("impact", {}))
    # Recency dominates (day-ordinal * 10 dwarfs the 1-4 impact); impact breaks same-day ties.
    return {"recency_rank": recency, "impact_rank": impact, "composite": float(recency * 10 + impact)}


# --- Finalize + write --------------------------------------------------------
def finalize(record: dict, *, kind: str = "threat", run_id: str | None = None) -> dict:
    """Run a draft through normalize -> gate -> sort_keys -> provenance -> schema.

    Mutates and returns it. Raises `schema.ValidationError` on any invalid field. No API calls.
    """
    record.setdefault("schema_version", models.SCHEMA_VERSION)
    _normalize(record)
    apply_gate(record)  # sets verification block + normalizes source_name from the allowlist
    record["sort_keys"] = compute_sort_keys(record, kind)
    models.stamp_provenance(record, layer="verify", run_id=run_id or models.new_run_id())
    schema.validate(record, kind)
    return record


def write(record: dict, *, kind: str = "threat", run_id: str | None = None) -> tuple[dict, str, bool]:
    """Finalize then write to the kind's published or quarantine dir by gate result."""
    rec = finalize(record, kind=kind, run_id=run_id)
    quarantined = rec["verification"]["status"] == "quarantined"
    path = store.write_record(rec, quarantine=quarantined, kind=kind)
    return rec, str(path), quarantined
