"""The deterministic author helper must run drafts through the same gate the pipeline uses."""

import copy

import pytest

from pipeline.curate import finalize
from pipeline.schema import ValidationError


def _draft(source_url):
    return {
        "id": "test-threat",
        "name": "Test Threat",
        "category": "geological",
        "description": "A description for a checkable test threat.",
        "assessment": {
            "probability": {"window": "next-100-years", "estimate": "very-low",
                            "numeric_annual": None},
            "severity": "continental",
            "timeframe": "No reliable short-term forecast.",
            "summary": "A one-sentence summary.",
        },
        "claims": [{
            "id": "claim-1",
            "text": "A checkable assertion.",
            "source_name": "Some Source",
            "source_url": source_url,
            "retrieved_date": "2026-06-30",
            "verification_status": "verified",
        }],
    }


def test_allowlisted_draft_finalizes_to_verified():
    rec = finalize(_draft("https://www.usgs.gov/x"))
    assert rec["verification"]["status"] == "verified"
    assert rec["claims"][0]["source_name"] == "USGS"  # normalized from the allowlist
    # severity continental=2, probability very-low=1 -> composite 2*10+1
    assert rec["sort_keys"] == {"severity_rank": 2, "probability_rank": 1, "composite": 21.0}
    assert rec["provenance"]["last_layer"] == "verify"
    assert rec["last_updated"]  # stamped


def test_non_allowlisted_draft_is_quarantined():
    rec = finalize(_draft("https://blog.example.com/post"))
    assert rec["claims"][0]["verification_status"] == "unverified"  # downgraded by the gate
    assert rec["verification"]["status"] == "quarantined"


def test_finalize_validates_and_rejects_bad_slug():
    bad = _draft("https://www.usgs.gov/x")
    bad["id"] = "Bad_Slug"  # uppercase + underscore violates ^[a-z0-9-]+$
    with pytest.raises(ValidationError):
        finalize(bad)


def test_finalize_is_self_contained_no_writes(tmp_path):
    # finalize() must not touch disk (only write() does) — safe to call freely.
    before = copy.deepcopy(_draft("https://www.usgs.gov/x"))
    rec = finalize(before)
    assert rec is before  # mutates in place, returns same object


def test_finalize_normalizes_whitespace():
    draft = _draft("https://www.usgs.gov/x")
    draft["name"] = "  Test Threat  "
    draft["assessment"]["summary"] = " A one-sentence summary. "
    draft["claims"][0]["text"] = "  A checkable assertion.  "
    rec = finalize(draft)
    assert rec["name"] == "Test Threat"
    assert rec["assessment"]["summary"] == "A one-sentence summary."
    assert rec["claims"][0]["text"] == "A checkable assertion."


def test_finalize_dedups_case_insensitive_duplicate_claims():
    draft = _draft("https://www.usgs.gov/x")
    dupe = dict(draft["claims"][0], id="claim-2", text="A CHECKABLE ASSERTION.")
    draft["claims"].append(dupe)
    rec = finalize(draft)
    assert len(rec["claims"]) == 1
    assert rec["claims"][0]["id"] == "claim-1"  # stable sort keeps the first id
