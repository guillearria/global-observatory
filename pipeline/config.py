"""Static configuration: paths, the source allowlist, and ranking tables.

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
# World Pulse events reuse the same trust spine as threats but live in their own
# dirs and schema (a dated occurrence, not a standing risk). See event.schema.json.
EVENTS_DIR = DATA_DIR / "events"
QUARANTINE_EVENTS_DIR = DATA_DIR / "quarantine-events"
EVENT_SCHEMA_PATH = DATA_DIR / "schema" / "event.schema.json"
FRONTEND_DATA = ROOT / "frontend" / "data" / "threats.json"
FRONTEND_EVENTS_DATA = ROOT / "frontend" / "data" / "events.json"
CHANGELOG_PATH = ROOT / "CHANGELOG.md"

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
    "wfp.org": "UN World Food Programme",
    "unep.org": "UN Environment Programme",
    "iea.org": "IEA",
    # societal / cross-cutting
    "un.org": "United Nations",
    "worldbank.org": "World Bank",
    "oecd.org": "OECD",
    "europa.eu": "European Union",  # EU institutions (only EU bodies use europa.eu)
    "ohchr.org": "UN Human Rights (OHCHR)",  # human-rights / atrocity indicators
    "unhcr.org": "UNHCR",  # forced displacement / refugee figures
    "unesco.org": "UNESCO",  # education / cultural / scientific indicators
    # technological (AI risk) — official quantified sources are scarce here.
    # NIST's AI Risk Management Framework was the only anchor; the additions
    # below are official government / intergovernmental AI bodies so
    # technological claims can verify instead of always quarantining.
    "nist.gov": "NIST",
    "aisi.gov.uk": "UK AI Security Institute",  # UK govt AI risk research body
    "oecd.ai": "OECD.AI",  # OECD AI Policy Observatory (intergovernmental)
    "itu.int": "ITU",  # UN specialized agency for ICT / AI standards
    # World Pulse (event) sourcing — disaster/crisis-specific authoritative feeds
    "gdacs.org": "GDACS",  # UN/EU-backed Global Disaster Alert and Coordination System
    "reliefweb.int": "ReliefWeb",  # UN OCHA's humanitarian crisis reporting service
    "imf.org": "IMF",  # for the "economic" event category, same tier as worldbank.org/oecd.org
}

# Severity / probability -> integer rank, used by curate.compute_sort_keys.
SEVERITY_RANK = {"regional": 1, "continental": 2, "civilizational": 3, "extinction": 4}
PROBABILITY_RANK = {"very-low": 1, "low": 2, "medium": 3, "high": 4, "very-high": 5}

# Event impact -> rank (1-4), used to break same-day ties in the World Pulse.
# Deaths and displaced are both considered; the larger signal decides. Ordered
# high-to-low so the first matching threshold wins. Below the smallest -> rank 1.
EVENT_IMPACT_DEATHS = [(1000, 4), (100, 3), (10, 2)]
EVENT_IMPACT_DISPLACED = [(1_000_000, 4), (100_000, 3), (10_000, 2)]


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
