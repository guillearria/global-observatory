"""The deterministic quarantine gate is the core trust defense — test it directly."""

import pytest

from pipeline.config import allowlisted
from pipeline.gate import apply_gate


def _claim(status, url="", sid="claim-1"):
    return {
        "id": sid,
        "text": "a checkable assertion",
        "source_name": "Some Source",
        "source_url": url,
        "retrieved_date": "2026-01-01",
        "verification_status": status,
    }


def _rec(claims):
    return {
        "id": "x",
        "claims": claims,
        "verification": {"status": "unverified", "confidence": "low", "notes": ""},
    }


def test_allowlisted_verified_claim_publishes():
    r = apply_gate(_rec([_claim("verified", "https://www.usgs.gov/x")]))
    assert r["verification"]["status"] == "verified"
    assert r["verification"]["confidence"] == "high"


def test_non_allowlisted_source_is_downgraded_and_quarantined():
    r = apply_gate(_rec([_claim("verified", "https://blog.example.com/post")]))
    assert r["claims"][0]["verification_status"] == "unverified"
    assert r["verification"]["status"] == "quarantined"


def test_disputed_claim_quarantines_even_with_a_verified_one():
    r = apply_gate(_rec([
        _claim("verified", "https://www.usgs.gov/a", "claim-1"),
        _claim("disputed", "https://www.who.int/b", "claim-2"),
    ]))
    assert r["verification"]["status"] == "quarantined"


def test_verified_plus_unverified_is_partial():
    r = apply_gate(_rec([
        _claim("verified", "https://www.usgs.gov/a", "claim-1"),
        _claim("unverified", "", "claim-2"),
    ]))
    assert r["verification"]["status"] == "partial"
    assert r["verification"]["confidence"] == "medium"


def test_no_verified_claim_quarantines():
    r = apply_gate(_rec([_claim("unverified", "", "claim-1")]))
    assert r["verification"]["status"] == "quarantined"


def test_source_name_normalized_to_allowlist_label():
    r = apply_gate(_rec([_claim("verified", "https://cneos.jpl.nasa.gov/x")]))
    assert r["claims"][0]["source_name"] == "NASA CNEOS"


@pytest.mark.parametrize(
    "url, label",
    [
        ("https://www.aisi.gov.uk/work", "UK AI Security Institute"),
        ("https://oecd.ai/en/dashboards", "OECD.AI"),
        ("https://www.itu.int/en/ai", "ITU"),
        ("https://www.ohchr.org/en/report", "UN Human Rights (OHCHR)"),
        ("https://www.unhcr.org/refugee-statistics", "UNHCR"),
        ("https://www.unesco.org/en/data", "UNESCO"),
        ("https://www.wfp.org/hunger-map", "UN World Food Programme"),
        ("https://digital-strategy.ec.europa.eu/en/ai-act", "European Union"),
        ("https://www.sipri.org/yearbook/2026", "SIPRI"),
    ],
)
def test_new_authoritative_domains_are_allowlisted(url, label):
    ok, got = allowlisted(url)
    assert ok and got == label


def test_specific_europa_subdomain_keeps_its_finer_label():
    # europa.eu is now allowlisted, but the more-specific ecdc.europa.eu must still win.
    ok, label = allowlisted("https://www.ecdc.europa.eu/en/flu")
    assert ok and label == "ECDC"


def test_new_domain_claim_publishes_through_gate():
    r = apply_gate(_rec([_claim("verified", "https://www.aisi.gov.uk/research")]))
    assert r["verification"]["status"] == "verified"
    assert r["claims"][0]["source_name"] == "UK AI Security Institute"
