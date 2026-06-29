#!/usr/bin/env python3
"""Aggregate data/threats/ and data/quarantine/ into frontend/data/threats.json."""

from pipeline import frontend


def main() -> None:
    doc = frontend.build()
    print(
        f"built frontend/data/threats.json — "
        f"{len(doc['published'])} published, {len(doc['under_review'])} under review"
    )


if __name__ == "__main__":
    main()
