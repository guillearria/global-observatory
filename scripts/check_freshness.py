#!/usr/bin/env python3
"""Check collection and ongoing-event freshness, optionally comparing the deployed data."""
import argparse
import json
import os
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


def collect_errors(live=False):
    now = datetime.now(UTC)
    errors = []
    for kind in LIMITS:
        data = json.loads(Path(f"frontend/data/{kind}.json").read_text())
        errors.extend(check_data(kind, data, now))
        if live:
            try:
                request = Request(f"{SITE}data/{kind}.json", headers={"Cache-Control": "no-cache"})
                with urlopen(request, timeout=30) as response:
                    deployed = json.load(response)
                errors.extend(check_data(kind, deployed, now))
                if deployed != data:
                    errors.append(f"{kind}: deployed aggregate differs from checked commit; inspect Pages")
            except (OSError, ValueError) as error:
                errors.append(f"{kind}: cannot verify deployed data: {error}")
    return errors


def report(errors, report_only=False):
    message = "\n".join(errors) if errors else "Collection and ongoing-event refresh checks passed"
    print(message)
    if errors and report_only:
        print("::warning::Refresh incomplete: valid updates may publish, but stale records remain. "
              "See the freshness summary and the independent staleness check.")
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        heading = "Freshness: incomplete" if errors else "Freshness: passed"
        with Path(summary).open("a") as handle:
            handle.write(f"## {heading}\n\n```text\n{message}\n```\n")
            if errors and report_only:
                handle.write("\nThis advisory does not block valid data publication or establish "
                             "complete research coverage. The post-deploy and daily staleness "
                             "checks remain strict.\n")
    return int(bool(errors) and not report_only)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="Compare deployed and committed data")
    parser.add_argument("--report-only", action="store_true",
                        help="Report incomplete freshness without blocking valid data publication")
    args = parser.parse_args(argv)
    raise SystemExit(report(collect_errors(live=args.live), report_only=args.report_only))


if __name__ == "__main__":
    main()
