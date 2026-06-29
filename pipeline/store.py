"""Atomic, deterministic file store. Git is the database; one JSON file per threat."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from . import config, models


def path_for(slug: str) -> Path:
    return config.THREATS_DIR / f"{slug}.json"


def quarantine_path_for(slug: str) -> Path:
    return config.QUARANTINE_DIR / f"{slug}.json"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_all() -> dict[str, dict]:
    """Map slug -> record for every published threat, sorted by slug."""
    out: dict[str, dict] = {}
    if not config.THREATS_DIR.exists():
        return out
    for p in sorted(config.THREATS_DIR.glob("*.json")):
        rec = load(p)
        out[rec["id"]] = rec
    return out


def write_atomic(path: Path, text: str) -> None:
    """Write via a temp file + os.replace so a crash never leaves a half-written record."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def write_record(record: dict, *, quarantine: bool = False) -> Path:
    slug = record["id"]
    path = quarantine_path_for(slug) if quarantine else path_for(slug)
    write_atomic(path, models.dumps(record))
    return path


def write_all(records: list[dict]) -> list[Path]:
    return [write_record(r) for r in records]


def write_quarantine(records: list[dict]) -> list[Path]:
    return [write_record(r, quarantine=True) for r in records]
