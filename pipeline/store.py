"""Atomic, deterministic file store. Git is the database; one JSON file per threat."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from . import config, models


# Lambdas, not frozen paths: dirs are read from `config` at call time so tests can
# `monkeypatch.setattr(config, "THREATS_DIR", ...)` for isolation (mirrors schema.py's
# _SCHEMA_PATHS, which has the same requirement for the same reason).
_KIND_DIRS: dict[str, tuple] = {
    "threat": (lambda: config.THREATS_DIR, lambda: config.QUARANTINE_DIR),
    "event": (lambda: config.EVENTS_DIR, lambda: config.QUARANTINE_EVENTS_DIR),
}


def dirs_for(kind: str = "threat") -> tuple[Path, Path]:
    """(published_dir, quarantine_dir) for a record kind. Threat is the default."""
    published, quarantine = _KIND_DIRS[kind]
    return published(), quarantine()


def path_for(slug: str, kind: str = "threat") -> Path:
    return dirs_for(kind)[0] / f"{slug}.json"


def quarantine_path_for(slug: str, kind: str = "threat") -> Path:
    return dirs_for(kind)[1] / f"{slug}.json"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_all(kind: str = "threat") -> dict[str, dict]:
    """Map slug -> record for every published record of a kind, sorted by slug."""
    out: dict[str, dict] = {}
    published_dir = dirs_for(kind)[0]
    if not published_dir.exists():
        return out
    for p in sorted(published_dir.glob("*.json")):
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


def write_record(record: dict, *, quarantine: bool = False, kind: str = "threat") -> Path:
    slug = record["id"]
    path = quarantine_path_for(slug, kind) if quarantine else path_for(slug, kind)
    write_atomic(path, models.dumps(record))
    return path
