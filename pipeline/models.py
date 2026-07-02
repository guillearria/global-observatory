"""Record helpers: deterministic serialization, ids, and provenance.

Records are plain dicts that mirror data/schema/threat.schema.json one-to-one. We keep
them as dicts (not dataclasses) so arbitrary nested JSON round-trips losslessly; this module
provides the invariants the curation path relies on.
"""

from __future__ import annotations

import json
import re
import secrets
from datetime import datetime, timezone

SCHEMA_VERSION = "1.0"
_SLUG_RE = re.compile(r"^[a-z0-9-]+$")
_HISTORY_CAP = 20


def dumps(record: dict) -> str:
    """Canonical on-disk form. Deterministic so git diffs are meaningful."""
    return json.dumps(record, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def slug_ok(slug: str) -> bool:
    return bool(_SLUG_RE.match(slug))


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def utc_now_compact() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")


def short_random() -> str:
    return secrets.token_hex(3)


def new_run_id() -> str:
    return f"{utc_now_compact()}-{short_random()}"


def _summary_of(r: dict, kind: str) -> str:
    if kind == "event":
        return r.get("event", {}).get("impact", {}).get("summary", "")
    return r.get("assessment", {}).get("summary", "")


def index_of(records: list[dict], kind: str = "threat") -> list[dict]:
    """Compact index fed to Generate (or a refresh command): slug/name/category/summary only.

    Deliberately excludes full claims so Generate cannot anchor on stale, possibly
    hallucinated prior text (ARCHITECTURE.md §5).
    """
    out = [
        {
            "id": r["id"],
            "name": r.get("name", ""),
            "category": r.get("category", ""),
            "summary": _summary_of(r, kind),
        }
        for r in records
    ]
    return sorted(out, key=lambda r: r["id"])


def stamp_provenance(record: dict, *, layer: str, run_id: str, at: str | None = None) -> dict:
    """Append-only provenance, capped so files don't grow unbounded. Mutates in place."""
    at = at or utc_now_iso()
    prov = record.setdefault("provenance", {"last_layer": layer, "last_run_id": run_id, "history": []})
    prov["last_layer"] = layer
    prov["last_run_id"] = run_id
    history = prov.setdefault("history", [])
    history.append({"layer": layer, "run_id": run_id, "at": at})
    prov["history"] = history[-_HISTORY_CAP:]
    record["last_updated"] = at
    return record
