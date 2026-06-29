"""Aggregate every record into the single JSON file the static frontend fetches.

Published (verified/partial) and under-review (quarantined) records go into separate sections so
the page can render the "unverified — under review" banner (Correction #2: quarantined threats are
surfaced, not hidden). Deterministic given fixed data — no timestamp of its own — so it only
changes when the underlying records do.
"""

from __future__ import annotations

import json

from . import config, store


def build() -> dict:
    published = [store.load(p) for p in sorted(config.THREATS_DIR.glob("*.json"))]
    under_review = (
        [store.load(p) for p in sorted(config.QUARANTINE_DIR.glob("*.json"))]
        if config.QUARANTINE_DIR.exists()
        else []
    )
    last_updated = max((r.get("last_updated", "") for r in published + under_review), default="")
    doc = {
        "last_updated": last_updated,
        "published": published,
        "under_review": under_review,
    }
    config.FRONTEND_DATA.parent.mkdir(parents=True, exist_ok=True)
    store.write_atomic(
        config.FRONTEND_DATA,
        json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
    )
    return doc
