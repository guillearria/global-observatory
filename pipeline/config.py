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
PROMPTS_DIR = ROOT / "pipeline" / "prompts"
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
    # technological (AI risk) — official quantified sources are scarce here
    # (ARCHITECTURE.md §11 #2). NIST's AI Risk Management Framework was the only
    # anchor; the additions below are official government / intergovernmental AI
    # bodies so technological claims can verify instead of always quarantining.
    "nist.gov": "NIST",
    "aisi.gov.uk": "UK AI Security Institute",  # UK govt AI risk research body
    "oecd.ai": "OECD.AI",  # OECD AI Policy Observatory (intergovernmental)
    "itu.int": "ITU",  # UN specialized agency for ICT / AI standards
}

# Severity / probability -> integer rank, used by the Optimize layer.
SEVERITY_RANK = {"regional": 1, "continental": 2, "civilizational": 3, "extinction": 4}
PROBABILITY_RANK = {"very-low": 1, "low": 2, "medium": 3, "high": 4, "very-high": 5}

# --- Pricing (USD) ---------------------------------------------------------
# Per-million-token list prices (input, output). Source: Anthropic pricing,
# cached 2026-06-04 via the claude-api reference. Update when prices change.
# Cache reads/writes are ignored here (this pipeline does no prompt caching).
PRICING = {
    "claude-opus-4-8": {"input": 5.00, "output": 25.00},
    "claude-sonnet-4-6": {"input": 3.00, "output": 15.00},
    "claude-haiku-4-5": {"input": 1.00, "output": 5.00},
}
# Web search server tool: USD per 1,000 searches (standard Anthropic rate).
WEB_SEARCH_COST_PER_1K = 10.00


def estimate_cost(model: str, input_tokens: int, output_tokens: int, web_searches: int = 0) -> float:
    """Rough USD cost for one model call. Unknown models cost 0 (logged as such)."""
    price = PRICING.get(model)
    if not price:
        return 0.0
    cost = input_tokens / 1_000_000 * price["input"]
    cost += output_tokens / 1_000_000 * price["output"]
    cost += web_searches / 1_000 * WEB_SEARCH_COST_PER_1K
    return cost


def load_prompt(name: str) -> str:
    """Read a system prompt by stem, e.g. load_prompt("generate")."""
    return (PROMPTS_DIR / f"{name}.system.md").read_text(encoding="utf-8")


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
