#!/usr/bin/env python3
"""Finalize a hand-drafted threat record through the deterministic, no-API trust guards.

Thin CLI over `pipeline.curate`. A draft is a published record minus the computed fields
(`verification`, `sort_keys`, `provenance`, `last_updated`, `schema_version`); it must contain
`id`, `name`, `category`, `description`, `assessment`, and `claims` (each with a real `source_url`
+ `retrieved_date`). The allowlist gate — not the drafter — decides verified vs quarantined.

Usage:
    python scripts/author_threat.py draft.json           # finalize one draft file
    cat draft.json | python scripts/author_threat.py -    # ... or from stdin
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from pipeline import curate


def main() -> None:
    ap = argparse.ArgumentParser(prog="author_threat", description=__doc__)
    ap.add_argument("draft", help="Path to a draft JSON file, or '-' to read from stdin.")
    args = ap.parse_args()

    raw = sys.stdin.read() if args.draft == "-" else Path(args.draft).read_text(encoding="utf-8")
    record = json.loads(raw)

    rec, path, quarantined = curate.write(record)
    v = rec["verification"]
    where = "quarantine" if quarantined else "published"
    print(
        f"{rec['id']}: {v['status']} ({v['confidence']}) -> {where}\n"
        f"  {v['notes']}\n"
        f"  sort_keys={rec['sort_keys']}\n"
        f"  wrote {path}"
    )
    if quarantined:
        print(
            "  NOTE: quarantined records are NOT published — at least one claim must cite an "
            "allowlisted authoritative domain to publish.",
            file=sys.stderr,
        )


if __name__ == "__main__":
    main()
