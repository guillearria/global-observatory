#!/usr/bin/env python3
"""Check collection and ongoing-event freshness, optionally comparing the deployed data."""
import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from urllib.request import Request, urlopen

LIMITS = {"events": 2, "threats": 10}
SITE = "https://guillearria.github.io/global-observatory/"


def check_data(kind, data, now):
    errors = []
    limit = LIMITS[kind]
    records = [(kind, data)]
    if kind == "events":
        records += [(r["id"], r) for r in data["published"]
                    if r.get("event", {}).get("status") == "ongoing"]
    for name, record in records:
        try:
            stamp = datetime.fromisoformat((record.get("last_updated") or "").replace("Z", "+00:00"))
            age = (now - stamp).total_seconds() / 86400
        except (ValueError, TypeError):
            errors.append(f"{name}: missing or invalid refresh date")
            continue
        if age > limit or age < -1:
            errors.append(f"{name}: refresh age {age:.1f} days (limit {limit})")
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="Compare deployed and committed data")
    args = parser.parse_args()
    now = datetime.now(UTC)
    errors = []
    for kind in LIMITS:
        data = json.loads(Path(f"frontend/data/{kind}.json").read_text())
        errors.extend(check_data(kind, data, now))
        if args.live:
            try:
                request = Request(f"{SITE}data/{kind}.json", headers={"Cache-Control": "no-cache"})
                with urlopen(request, timeout=30) as response:
                    live = json.load(response)
                errors.extend(check_data(kind, live, now))
                if live != data:
                    errors.append(f"{kind}: deployed aggregate differs from main; inspect Pages")
            except (OSError, ValueError) as error:
                errors.append(f"{kind}: cannot verify deployed data: {error}")
    print("\n".join(errors) if errors else "Collection and ongoing-event refresh checks passed")
    raise SystemExit(bool(errors))


if __name__ == "__main__":
    main()
