"""Aggregate every record into the single JSON file the static frontend fetches.

Published (verified/partial) and under-review (quarantined) records go into separate sections so
the page can render the "unverified — under review" banner (Correction #2: quarantined threats are
surfaced, not hidden). Deterministic given fixed data — no timestamp of its own — so it only
changes when the underlying records do.
"""

from __future__ import annotations

import json

from . import config, store


def _aggregate(published_dir, quarantine_dir, out_path) -> dict:
    published = (
        [store.load(p) for p in sorted(published_dir.glob("*.json"))]
        if published_dir.exists()
        else []
    )
    under_review = (
        [store.load(p) for p in sorted(quarantine_dir.glob("*.json"))]
        if quarantine_dir.exists()
        else []
    )
    last_updated = max((r.get("last_updated", "") for r in published + under_review), default="")
    doc = {
        "last_updated": last_updated,
        "published": published,
        "under_review": under_review,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    store.write_atomic(
        out_path,
        json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
    )
    return doc


def build() -> dict:
    """Aggregate threats -> frontend/data/threats.json."""
    return _aggregate(config.THREATS_DIR, config.QUARANTINE_DIR, config.FRONTEND_DATA)


def build_events() -> dict:
    """Aggregate World Pulse events -> frontend/data/events.json."""
    return _aggregate(config.EVENTS_DIR, config.QUARANTINE_EVENTS_DIR, config.FRONTEND_EVENTS_DATA)


def build_historical() -> dict:
    """Aggregate Historical Archive records -> frontend/data/historical.json."""
    return _aggregate(
        config.HISTORICAL_DIR, config.QUARANTINE_HISTORICAL_DIR, config.FRONTEND_HISTORICAL_DATA
    )
