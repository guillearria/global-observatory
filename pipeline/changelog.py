"""Regenerate CHANGELOG.md from git history. The git log IS the changelog; this is a projection.

Walks `git log --name-status` over data/threats/ and data/quarantine/ and renders dated
sections per commit listing added / updated / quarantined slugs.
"""

from __future__ import annotations

import subprocess

from . import config

_FMT = "%x00C%x00%h%x00%ad%x00%s"


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=str(config.ROOT),
        capture_output=True,
        text=True,
        check=True,
    ).stdout


def _collect() -> list[dict]:
    out = _git(
        "log",
        "--name-status",
        "--date=short",
        f"--pretty=format:{_FMT}",
        "--",
        "data/threats",
        "data/quarantine",
    )
    commits: list[dict] = []
    cur: dict | None = None
    for line in out.splitlines():
        if line.startswith("\x00C\x00"):
            if cur:
                commits.append(cur)
            _, _tag, h, date, subject = line.split("\x00")
            cur = {"hash": h, "date": date, "subject": subject,
                   "added": [], "updated": [], "quarantined": []}
        elif line.strip() and cur is not None and "\t" in line:
            parts = line.split("\t")
            status, path = parts[0], parts[-1]
            slug = path.rsplit("/", 1)[-1].removesuffix(".json")
            if path.startswith("data/quarantine/") and status[0] in "AM":
                cur["quarantined"].append(slug)
            elif path.startswith("data/threats/") and status[0] == "A":
                cur["added"].append(slug)
            elif path.startswith("data/threats/") and status[0] == "M":
                cur["updated"].append(slug)
    if cur:
        commits.append(cur)
    return commits


def render() -> str:
    lines = [
        "# Changelog",
        "",
        "_Generated from git history over `data/threats/` and `data/quarantine/` by "
        "`pipeline.changelog`. Do not edit by hand._",
        "",
    ]
    for c in _collect():
        if not (c["added"] or c["updated"] or c["quarantined"]):
            continue
        lines.append(f"## {c['date']} — {c['subject']} (`{c['hash']}`)")
        lines.append("")
        for label, key in (("Added", "added"), ("Updated", "updated"), ("Quarantined", "quarantined")):
            slugs = sorted(set(c[key]))
            if slugs:
                lines.append(f"- **{label}:** {', '.join(slugs)}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def regenerate() -> str:
    text = render()
    config.CHANGELOG_PATH.write_text(text, encoding="utf-8")
    return text
