#!/usr/bin/env python3
"""Aggregate threats, World Pulse events, and the Historical Archive into frontend/data/*.json."""

from pipeline import frontend


def main() -> None:
    threats = frontend.build()
    events = frontend.build_events()
    historical = frontend.build_historical()
    print(
        f"built frontend/data/threats.json — "
        f"{len(threats['published'])} published, {len(threats['under_review'])} under review\n"
        f"built frontend/data/events.json — "
        f"{len(events['published'])} published, {len(events['under_review'])} under review\n"
        f"built frontend/data/historical.json — "
        f"{len(historical['published'])} published, {len(historical['under_review'])} under review"
    )


if __name__ == "__main__":
    main()
