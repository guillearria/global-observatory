#!/usr/bin/env python3
"""Schema-validate every published and quarantined record. Non-zero exit is the CI hard gate."""

import sys

from pipeline import config, schema, store


def _validate_dir(directory, kind: str = "threat") -> list[str]:
    errs: list[str] = []
    if not directory.exists():
        return errs
    for p in sorted(directory.glob("*.json")):
        try:
            rec = store.load(p)
        except Exception as e:  # noqa: BLE001 — report any unreadable file
            errs.append(f"{p.name}: could not parse ({e})")
            continue
        if rec.get("id") != p.stem:
            errs.append(f"{p.name}: id {rec.get('id')!r} does not match filename")
        try:
            schema.validate(rec, kind)
        except schema.ValidationError as e:
            errs.append(f"{p.name}: {e}")
    return errs


def _count(directory) -> int:
    return len(list(directory.glob("*.json"))) if directory.exists() else 0


def main() -> None:
    errs = (
        _validate_dir(config.THREATS_DIR, "threat")
        + _validate_dir(config.QUARANTINE_DIR, "threat")
        + _validate_dir(config.EVENTS_DIR, "event")
        + _validate_dir(config.QUARANTINE_EVENTS_DIR, "event")
        + _validate_dir(config.HISTORICAL_DIR, "historical")
        + _validate_dir(config.QUARANTINE_HISTORICAL_DIR, "historical")
    )
    for e in errs:
        print("FAIL", e)
    if errs:
        sys.exit(1)
    print(
        f"OK: validated {_count(config.THREATS_DIR)} threats "
        f"(+{_count(config.QUARANTINE_DIR)} quarantined), "
        f"{_count(config.EVENTS_DIR)} events (+{_count(config.QUARANTINE_EVENTS_DIR)} quarantined), "
        f"{_count(config.HISTORICAL_DIR)} historical "
        f"(+{_count(config.QUARANTINE_HISTORICAL_DIR)} quarantined)"
    )


if __name__ == "__main__":
    main()
