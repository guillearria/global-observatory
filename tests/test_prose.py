"""Prose discipline applies across kinds — with the two deliberate carve-outs.

The forbidden-phrase list and length caps (pipeline/config.py) keep description and
the kind summary current-state prose. Two measured exceptions from the live data:
"allowlisted" is legitimate in historical sourcing caveats (events-only ban), and
bare "correction" is legitimate event prose (a market correction) so it is not on
the list at all.
"""

import pytest

from pipeline.curate import finalize
from pipeline.schema import ValidationError, validate


def _threat_draft(source_url="https://www.who.int/x"):
    return {
        "id": "test-threat",
        "name": "Test Threat",
        "category": "biological",
        "description": "A checkable test threat.",
        "assessment": {
            "probability": {"window": "10 years", "estimate": "low"},
            "severity": "continental",
            "timeframe": "ongoing",
            "summary": "A checkable assessment.",
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


def _historical_draft(source_url="https://www.britannica.com/x"):
    return {
        "id": "test-historical",
        "name": "Test Historical Event",
        "category": "pandemic",
        "description": "A checkable test historical record.",
        "historical": {
            "year_start": 165,
            "year_end": 180,
            "date_display": "165–180 CE",
            "era": "classical",
            "location": {"country": "Roman Empire", "region": "Mediterranean basin"},
            "impact": {
                "deaths_low": 5_000_000,
                "deaths_high": 10_000_000,
                "summary": "Estimates range from 5 to 10 million deaths.",
            },
        },
        "claims": [{
            "id": "claim-1",
            "text": "A checkable assertion.",
            "source_name": "Some Source",
            "source_url": source_url,
            "retrieved_date": "2026-07-05",
            "verification_status": "verified",
        }],
    }


def _event_draft(source_url="https://earthquake.usgs.gov/x"):
    return {
        "id": "test-event",
        "name": "Test Event",
        "category": "earthquake",
        "description": "A checkable test event.",
        "event": {
            "occurrence_date": "2026-06-25",
            "location": {"country": "Venezuela", "region": "Near Moron"},
            "status": "ongoing",
            "scale": "M7.5",
            "impact": {"deaths": 12, "displaced": 5000, "summary": "Figures as of 2026-06-30."},
            "live_source_url": "https://earthquake.usgs.gov/earthquakes/eventpage/x",
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


def test_threat_prose_rejects_shared_phrases():
    bad = _threat_draft()
    bad["assessment"]["summary"] = "Re-verified 4 August 2026: assessment unchanged."
    with pytest.raises(ValidationError):
        finalize(bad)


def test_threat_description_cap():
    bad = _threat_draft()
    bad["description"] = "y" * 1201
    with pytest.raises(ValidationError):
        finalize(bad)


def test_historical_summary_may_say_allowlisted():
    # The antonine-plague/vesuvius precedent: sourcing caveats in historical
    # summaries legitimately name the allowlist. The ban is events-only.
    ok = _historical_draft()
    ok["historical"]["impact"]["summary"] = (
        "One higher figure could not be verified against any allowlisted source "
        "and is not adopted here."
    )
    rec = finalize(ok, kind="historical")
    assert rec["verification"]["status"] == "verified"


def test_historical_prose_rejects_shared_phrases():
    bad = _historical_draft()
    bad["description"] = "Re-checked against the archive on 5 July 2026."
    with pytest.raises(ValidationError):
        finalize(bad, kind="historical")


def test_bare_correction_is_allowed_in_event_prose():
    # The south-korea precedent: "correction" is ordinary market prose. Only the
    # specific process markers are forbidden, never the bare word.
    ok = _event_draft()
    ok["event"]["impact"]["summary"] = (
        "The index underwent a sizable correction amid heightened volatility."
    )
    rec = finalize(ok, kind="event")
    assert rec["verification"]["status"] == "verified"


def test_stored_updates_must_be_newest_first():
    # finalize sorts, but validate_data.py checks stored files directly — a
    # hand-edited out-of-order updates[] must be reported, not silently accepted.
    rec = finalize(_event_draft(), kind="event")
    rec["updates"] = [
        {"date": "2026-06-26", "text": "Toll revised to 12."},
        {"date": "2026-06-28", "text": "Displacement figure doubled."},
    ]
    with pytest.raises(ValidationError):
        validate(rec, "event")
