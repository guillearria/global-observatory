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
    python scripts/author_event.py --condense draft.json # draft deliberately merges updates[]

A draft that drops entries from the existing record's `updates[]` is refused unless `--condense`
is passed. Pass it only when every removed entry has been folded into an entry the draft keeps
(see "Condensing updates[]" in .claude/commands/refresh-events.md) — never to trim the log to fit
the cap. The removed entries are printed either way.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from pipeline import curate, store


def _previous(slug: object) -> dict | None:
    """The record currently on disk for this slug (published, else quarantined), if any."""
    if not isinstance(slug, str) or not slug:
        return None
    for path in (store.path_for(slug, "event"), store.quarantine_path_for(slug, "event")):
        if path.exists():
            return store.load(path)
    return None


def main() -> None:
    ap = argparse.ArgumentParser(prog="author_event", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("draft", help="Path to a draft JSON file, or '-' to read from stdin.")
    ap.add_argument("--condense", action="store_true",
                    help="Allow the draft to drop existing updates[] entries it has merged.")
    args = ap.parse_args()

    raw = sys.stdin.read() if args.draft == "-" else Path(args.draft).read_text(encoding="utf-8")
    record = json.loads(raw)

    dropped = curate.dropped_updates(_previous(record.get("id")), record)
    if dropped:
        verb = "condensing away" if args.condense else "would drop"
        print(f"{record['id']}: {verb} {len(dropped)} existing updates[] entr"
              f"{'y' if len(dropped) == 1 else 'ies'}:", file=sys.stderr)
        for u in dropped:
            print(f"  - {u.get('date')}: {str(u.get('text', ''))[:160]}", file=sys.stderr)
        if not args.condense:
            sys.exit(
                "Refusing: updates[] is a public timeline — never delete entries to fit the cap. "
                "Fold them into a kept summary entry (milestones stay as their own entries), then "
                "re-run with --condense. See 'Condensing updates[]' in "
                ".claude/commands/refresh-events.md."
            )

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
