"""Static configuration: paths, the source allowlist, and ranking tables.

Kept side-effect free so every other module and the tests can import it cheaply. The one
exception is the source allowlist, which is read from `data/source-allowlist.json` at import
(see below) — it is curated data, not code, so that refresh runs can extend it through the
same auto-publish path as records.
"""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlparse

# --- Paths -----------------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
THREATS_DIR = DATA_DIR / "threats"
QUARANTINE_DIR = DATA_DIR / "quarantine"
SCHEMA_PATH = DATA_DIR / "schema" / "threat.schema.json"
# World Pulse events reuse the same trust spine as threats but live in their own
# dirs and schema (a dated occurrence, not a standing risk). See event.schema.json.
EVENTS_DIR = DATA_DIR / "events"
QUARANTINE_EVENTS_DIR = DATA_DIR / "quarantine-events"
EVENT_SCHEMA_PATH = DATA_DIR / "schema" / "event.schema.json"
# Historical Archive records: major events from the dawn of civilization onward. Same
# trust spine again; chronology replaces recency (signed astronomical years, because
# date.toordinal cannot represent BCE dates). See historical.schema.json.
HISTORICAL_DIR = DATA_DIR / "historical"
QUARANTINE_HISTORICAL_DIR = DATA_DIR / "quarantine-historical"
HISTORICAL_SCHEMA_PATH = DATA_DIR / "schema" / "historical.schema.json"
FRONTEND_DATA = ROOT / "frontend" / "data" / "threats.json"
FRONTEND_EVENTS_DATA = ROOT / "frontend" / "data" / "events.json"
FRONTEND_HISTORICAL_DATA = ROOT / "frontend" / "data" / "historical.json"
CHANGELOG_PATH = ROOT / "CHANGELOG.md"

# --- Source allowlist ------------------------------------------------------
# The trust root. A claim is only considered `verified` when its citation host is,
# or is a subdomain of, a domain on this list. Subdomains match automatically (e.g.
# cneos.jpl.nasa.gov matches nasa.gov), so the finer-grained entries exist only to
# provide a better label.
#
# This lives in data/, not here, because refresh runs may extend it: a domain the
# curation path can add is data by definition. Each entry carries a written
# justification (enforced by data/schema/source-allowlist.schema.json and checked by
# scripts/validate_data.py) — with no review step, that justification and the
# CHANGELOG entry are the only record of why a domain came to be trusted.
SOURCE_ALLOWLIST_PATH = DATA_DIR / "source-allowlist.json"
SOURCE_ALLOWLIST_SCHEMA_PATH = DATA_DIR / "schema" / "source-allowlist.schema.json"


def _load_source_allowlist() -> dict[str, str]:
    """Read the allowlist data file into the domain -> label map `allowlisted` uses."""
    raw = json.loads(SOURCE_ALLOWLIST_PATH.read_text(encoding="utf-8"))
    return {entry["domain"]: entry["label"] for entry in raw["sources"]}


SOURCE_ALLOWLIST: dict[str, str] = _load_source_allowlist()

# Severity / probability -> integer rank, used by curate.compute_sort_keys.
SEVERITY_RANK = {"regional": 1, "continental": 2, "civilizational": 3, "extinction": 4}
PROBABILITY_RANK = {"very-low": 1, "low": 2, "medium": 3, "high": 4, "very-high": 5}

# Event impact -> rank (1-4), used to break same-day ties in the World Pulse.
# Deaths and displaced are both considered; the larger signal decides. Ordered
# high-to-low so the first matching threshold wins. Below the smallest -> rank 1.
EVENT_IMPACT_DEATHS = [(1000, 4), (100, 3), (10, 2)]
EVENT_IMPACT_DISPLACED = [(1_000_000, 4), (100_000, 3), (10_000, 2)]

# Historical impact -> rank (1-5), banded on the midpoint of the deaths_low/deaths_high
# estimate range (historical tolls are ranges, not counts). Ordered high-to-low so the
# first matching threshold wins. Below the smallest -> rank 1.
HISTORICAL_IMPACT_DEATHS = [(10_000_000, 5), (1_000_000, 4), (100_000, 3), (10_000, 2)]

# Historical chronology uses astronomical year numbering (0 = 1 BCE, -2999 = 3000 BCE),
# which date.toordinal cannot represent. chronology_rank = year_start + offset keeps the
# rank positive across the whole supported window (year -9999 -> rank 1).
HISTORICAL_YEAR_OFFSET = 10_000
HISTORICAL_YEAR_MIN = -9_999
HISTORICAL_YEAR_MAX = 2_100


def allowlisted(url: str) -> tuple[bool, str | None]:
    """Return (is_allowlisted, canonical_label) for a citation URL.

    Matches the host against each allowlist domain exactly or as a subdomain.
    The most specific matching domain wins (so cneos.jpl.nasa.gov -> "NASA CNEOS").
    """
    try:
        host = (urlparse(url).hostname or "").lower()
    except ValueError:
        return False, None
    if not host:
        return False, None
    best: tuple[int, str] | None = None
    for domain, label in SOURCE_ALLOWLIST.items():
        if host == domain or host.endswith("." + domain):
            specificity = domain.count(".")
            if best is None or specificity > best[0]:
                best = (specificity, label)
    if best is None:
        return False, None
    return True, best[1]
