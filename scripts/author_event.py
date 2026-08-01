#!/usr/bin/env python3
"""Finalize a hand-drafted World Pulse event through the deterministic, no-API trust guards.

Thin CLI over `pipeline.curate` (kind="event"). A draft is a published event minus the fields
computed here (`verification`, `sort_keys`, `provenance`, `last_updated`, `schema_version`); it must
contain `id`, `name`, `category`, `description`, `event`, and `claims` (each with a real `source_url`
+ `retrieved_date`). The allowlist gate — not the drafter — decides verified vs quarantined, exactly
as it does for threats.

Usage:
    python scripts/author_event.py draft.json           # finalize one draft file
    cat draft.json | python scripts/author_event.py -    # ... or from stdin
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from pipeline import curate


def main() -> None:
    ap = argparse.ArgumentParser(prog="author_event", description=__doc__)
    ap.add_argument("draft", help="Path to a draft JSON file, or '-' to read from stdin.")
    args = ap.parse_args()

    raw = sys.stdin.read() if args.draft == "-" else Path(args.draft).read_text(encoding="utf-8")
    record = json.loads(raw)

    rec, path, quarantined = curate.write(record, kind="event")
    v = rec["verification"]
    where = "quarantine-events" if quarantined else "published"
    print(
        f"{rec['id']}: {v['status']} ({v['confidence']}) -> {where}\n"
        f"  {v['notes']}\n"
        f"  sort_keys={rec['sort_keys']}\n"
        f"  wrote {path}"
    )
    if quarantined:
        print(
            "  NOTE: quarantined events are NOT published — at least one claim must cite an "
            "allowlisted authoritative domain to publish.",
            file=sys.stderr,
        )


if __name__ == "__main__":
    main()
