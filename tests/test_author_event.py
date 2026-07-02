"""World Pulse events run through the same deterministic gate as threats (kind='event')."""

import copy

import pytest

from pipeline.curate import _impact_rank, _recency_rank, finalize
from pipeline.schema import ValidationError


def _draft(source_url, **event_overrides):
    event = {
        "occurrence_date": "2026-06-25",
        "location": {"country": "Venezuela", "region": "Near Moron"},
        "status": "ongoing",
        "scale": "M7.5",
        "impact": {"deaths": 12, "displaced": 5000, "summary": "Figures as of 2026-06-30."},
        "live_source_url": "https://earthquake.usgs.gov/earthquakes/eventpage/x",
    }
    event.update(event_overrides)
    return {
        "id": "test-event",
        "name": "Test Event",
        "category": "earthquake",
        "description": "A checkable test event.",
        "event": event,
        "claims": [{
            "id": "claim-1",
            "text": "A checkable assertion.",
            "source_name": "Some Source",
            "source_url": source_url,
            "retrieved_date": "2026-06-30",
            "verification_status": "verified",
        }],
    }


def test_allowlisted_event_finalizes_to_verified():
    rec = finalize(_draft("https://earthquake.usgs.gov/earthquakes/eventpage/x"), kind="event")
    assert rec["verification"]["status"] == "verified"
    assert rec["claims"][0]["source_name"] == "USGS"  # normalized from the allowlist
    # recency = ordinal of 2026-06-25; impact_rank 2 (12 deaths -> band >=10); composite recency*10+2
    assert rec["sort_keys"]["impact_rank"] == 2
    assert rec["sort_keys"]["recency_rank"] > 0
    assert rec["sort_keys"]["composite"] == rec["sort_keys"]["recency_rank"] * 10 + 2
    assert rec["provenance"]["last_layer"] == "verify"
    assert rec["last_updated"]


def test_non_allowlisted_event_is_quarantined():
    rec = finalize(_draft("https://news.example.com/story"), kind="event")
    assert rec["claims"][0]["verification_status"] == "unverified"  # downgraded by the gate
    assert rec["verification"]["status"] == "quarantined"


def test_event_rejects_bad_slug():
    bad = _draft("https://earthquake.usgs.gov/x")
    bad["id"] = "Bad_Slug"
    with pytest.raises(ValidationError):
        finalize(bad, kind="event")


def test_event_schema_has_no_lat_lon_or_magnitude():
    # Phase 1 dropped lat/lon/magnitude: unused by any consumer, always null in real
    # seed data. additionalProperties: false means the schema now rejects them outright.
    bad = _draft("https://earthquake.usgs.gov/x")
    bad["event"]["location"]["lat"] = 10.5
    with pytest.raises(ValidationError):
        finalize(bad, kind="event")


def test_recency_rank_orders_by_date():
    assert _recency_rank("2026-06-25") > _recency_rank("2026-05-15") > _recency_rank("2023-04-15")
    assert _recency_rank("not-a-date") == 0


def test_impact_rank_bands():
    assert _impact_rank({"deaths": 2000, "displaced": None}) == 4
    assert _impact_rank({"deaths": None, "displaced": 1_000_000}) == 4
    assert _impact_rank({"deaths": 150, "displaced": None}) == 3
    assert _impact_rank({"deaths": 12, "displaced": 5000}) == 2
    assert _impact_rank({"deaths": None, "displaced": None}) == 1


def test_finalize_mutates_in_place_no_writes():
    before = copy.deepcopy(_draft("https://earthquake.usgs.gov/x"))
    rec = finalize(before, kind="event")
    assert rec is before
