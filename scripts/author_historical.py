#!/usr/bin/env python3
"""Finalize a hand-drafted Historical Archive record through the deterministic, no-API trust guards.

Thin CLI over `pipeline.curate` (kind="historical"). A draft is a published record minus the fields
computed here (`verification`, `sort_keys`, `provenance`, `last_updated`, `schema_version`); it must
contain `id`, `name`, `category`, `description`, `historical`, and `claims` (each with a real
`source_url` + `retrieved_date`). The allowlist gate — not the drafter — decides verified vs
quarantined, exactly as it does for threats and events.

Usage:
    python scripts/author_historical.py draft.json           # finalize one draft file
    cat draft.json | python scripts/author_historical.py -    # ... or from stdin
"""

from __future__ import annotations

import argparse
import json
import sys

from pipeline import curate


def main() -> None:
    ap = argparse.ArgumentParser(prog="author_historical", description=__doc__)
    ap.add_argument("draft", help="Path to a draft JSON file, or '-' to read from stdin.")
    args = ap.parse_args()

    raw = sys.stdin.read() if args.draft == "-" else open(args.draft, encoding="utf-8").read()
    record = json.loads(raw)

    rec, path, quarantined = curate.write(record, kind="historical")
    v = rec["verification"]
    where = "quarantine-historical" if quarantined else "published"
    print(
        f"{rec['id']}: {v['status']} ({v['confidence']}) -> {where}\n"
        f"  {v['notes']}\n"
        f"  sort_keys={rec['sort_keys']}\n"
        f"  wrote {path}"
    )
    if quarantined:
        print(
            "  NOTE: quarantined historical records are NOT published — at least one claim must "
            "cite an allowlisted authoritative domain (the scholarly tier counts) to publish.",
            file=sys.stderr,
        )


if __name__ == "__main__":
    main()
