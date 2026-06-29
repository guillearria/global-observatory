"""Static configuration: paths, model/effort tiers, web tools, and the source allowlist.

Kept side-effect free so every other module and the tests can import it cheaply.
"""

from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse

# --- Paths -----------------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
THREATS_DIR = DATA_DIR / "threats"
QUARANTINE_DIR = DATA_DIR / "quarantine"
SCHEMA_PATH = DATA_DIR / "schema" / "threat.schema.json"
FRONTEND_DATA = ROOT / "frontend" / "data" / "threats.json"
CHANGELOG_PATH = ROOT / "CHANGELOG.md"
FIXTURES_DIR = ROOT / "tests" / "fixtures"

# --- Models ----------------------------------------------------------------
MODEL_GENERATE = "claude-opus-4-8"
MODEL_VERIFY = "claude-opus-4-8"
MODEL_CLEANUP = "claude-haiku-4-5"
MODEL_OPTIMIZE = "claude-sonnet-4-6"

# Effort tier per layer. None => omit the parameter entirely.
# Haiku does not support `effort`, so Clean-up is None.
EFFORT_GENERATE = "high"
EFFORT_VERIFY = "high"
EFFORT_CLEANUP = None
EFFORT_OPTIMIZE = "medium"

# Correction #1: adaptive thinking is a Claude 4.6+ feature. Haiku 4.5 is a
# 4.5-generation model and may 400 on thinking={"type":"adaptive"} (it already
# rejects `effort`). Until scripts/probe_haiku.py confirms otherwise we omit
# thinking for these models. client.thinking_for() reads this set.
NO_ADAPTIVE_THINKING = {"claude-haiku-4-5"}

MAX_TOKENS = 16000

# --- Server tools (current variants for Opus 4.8 / Sonnet 4.6) --------------
WEB_SEARCH_TOOL = {"type": "web_search_20260209", "name": "web_search", "max_uses": 5}
WEB_FETCH_TOOL = {"type": "web_fetch_20260209", "name": "web_fetch", "max_uses": 5}

# --- Source allowlist ------------------------------------------------------
# A claim is only considered `verified` when its citation host is, or is a
# subdomain of, a domain on this list. Map domain -> canonical source label.
# Subdomains match automatically (e.g. cneos.jpl.nasa.gov matches nasa.gov),
# so the finer-grained entries below exist only to provide a better label.
SOURCE_ALLOWLIST: dict[str, str] = {
    # geological / climate / cosmic
    "usgs.gov": "USGS",
    "noaa.gov": "NOAA",
    "nasa.gov": "NASA",
    "cneos.jpl.nasa.gov": "NASA CNEOS",
    "jpl.nasa.gov": "NASA JPL",
    "ipcc.ch": "IPCC",
    "ipbes.net": "IPBES",
    # biological / health
    "who.int": "WHO",
    "cdc.gov": "CDC",
    "ecdc.europa.eu": "ECDC",
    # nuclear
    "iaea.org": "IAEA",
    # resource (food / water / energy)
    "fao.org": "FAO",
    "unep.org": "UN Environment Programme",
    "iea.org": "IEA",
    # societal / cross-cutting
    "un.org": "United Nations",
    "worldbank.org": "World Bank",
    "oecd.org": "OECD",
    # technological (AI risk) — official quantified sources are scarce here
    # (ARCHITECTURE.md §11 #2). NIST's AI Risk Management Framework is the most
    # defensible authoritative anchor; categories without coverage will tend to
    # quarantine until more sources are added.
    "nist.gov": "NIST",
}

# Severity / probability -> integer rank, used by the Optimize layer.
SEVERITY_RANK = {"regional": 1, "continental": 2, "civilizational": 3, "extinction": 4}
PROBABILITY_RANK = {"very-low": 1, "low": 2, "medium": 3, "high": 4, "very-high": 5}


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
