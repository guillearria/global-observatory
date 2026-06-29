#!/usr/bin/env python3
"""Schema-validate every published and quarantined record. Non-zero exit is the CI hard gate."""

import sys

from pipeline import config, schema, store


def _validate_dir(directory) -> list[str]:
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
            schema.validate(rec)
        except schema.ValidationError as e:
            errs.append(f"{p.name}: {e}")
    return errs


def main() -> None:
    errs = _validate_dir(config.THREATS_DIR) + _validate_dir(config.QUARANTINE_DIR)
    for e in errs:
        print("FAIL", e)
    if errs:
        sys.exit(1)
    published = len(list(config.THREATS_DIR.glob("*.json")))
    quarantined = len(list(config.QUARANTINE_DIR.glob("*.json"))) if config.QUARANTINE_DIR.exists() else 0
    print(f"OK: validated {published} published + {quarantined} quarantined records")


if __name__ == "__main__":
    main()
