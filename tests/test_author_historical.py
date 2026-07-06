"""Historical Archive records run through the same deterministic gate (kind='historical')."""

import copy

import pytest

from pipeline.curate import _chronology_rank, _historical_impact_rank, finalize
from pipeline.schema import ValidationError


def _draft(source_url, **historical_overrides):
    historical = {
        "year_start": 1347,
        "year_end": 1351,
        "date_display": "1347–1351",
        "era": "medieval",
        "location": {"country": "Eurasia and North Africa", "region": "Spread along trade routes from Central Asia"},
        "impact": {
            "deaths_low": 75_000_000,
            "deaths_high": 200_000_000,
            "summary": "Estimates range from 75 to 200 million deaths across Eurasia and North Africa.",
        },
    }
    historical.update(historical_overrides)
    return {
        "id": "test-historical",
        "name": "Test Historical Event",
        "category": "pandemic",
        "description": "A checkable test historical record.",
        "historical": historical,
        "claims": [{
            "id": "claim-1",
            "text": "A checkable assertion.",
            "source_name": "Some Source",
            "source_url": source_url,
            "retrieved_date": "2026-07-05",
            "verification_status": "verified",
        }],
    }


def test_scholarly_source_finalizes_to_verified():
    rec = finalize(_draft("https://www.britannica.com/event/Black-Death"), kind="historical")
    assert rec["verification"]["status"] == "verified"
    assert rec["claims"][0]["source_name"] == "Encyclopaedia Britannica"  # normalized
    # 1347 + 10000 offset; 75-200M midpoint -> top impact band; composite chronology-dominant
    assert rec["sort_keys"]["chronology_rank"] == 11347
    assert rec["sort_keys"]["impact_rank"] == 5
    assert rec["sort_keys"]["composite"] == 11347 * 10 + 5
    assert rec["provenance"]["last_layer"] == "verify"
    assert rec["last_updated"]


def test_non_allowlisted_source_is_quarantined():
    rec = finalize(_draft("https://myhistoryblog.example.com/black-death"), kind="historical")
    assert rec["claims"][0]["verification_status"] == "unverified"  # downgraded by the gate
    assert rec["verification"]["status"] == "quarantined"


def test_chronology_rank_is_bce_capable():
    # Astronomical numbering: 3000 BCE = -2999; date.toordinal could never express this.
    assert _chronology_rank(-2999) == 7001
    assert _chronology_rank(0) == 10_000  # 1 BCE
    assert _chronology_rank(1918) == 11_918
    assert _chronology_rank(-1176) < _chronology_rank(1918)  # BCE sorts before CE
    assert _chronology_rank("1918") == 0  # non-int -> 0, rejected by the range check
    assert _chronology_rank(None) == 0


def test_historical_impact_rank_bands():
    mk = lambda lo, hi: {"deaths_low": lo, "deaths_high": hi}  # noqa: E731
    assert _historical_impact_rank(mk(75_000_000, 200_000_000)) == 5
    assert _historical_impact_rank(mk(1_000_000, None)) == 4  # one bound alone counts
    assert _historical_impact_rank(mk(60_000, 200_000)) == 3  # midpoint 130k -> band 3
    assert _historical_impact_rank(mk(50_000, None)) == 2
    assert _historical_impact_rank(mk(None, None)) == 1  # unquantified
    assert _historical_impact_rank({}) == 1


def test_year_end_before_year_start_rejected():
    bad = _draft("https://www.britannica.com/x", year_end=1300)
    with pytest.raises(ValidationError):
        finalize(bad, kind="historical")


def test_year_out_of_supported_window_rejected():
    bad = _draft("https://www.britannica.com/x", year_start=-20_000, year_end=None)
    with pytest.raises(ValidationError):
        finalize(bad, kind="historical")


def test_deaths_low_above_deaths_high_rejected():
    bad = _draft(
        "https://www.britannica.com/x",
        impact={"deaths_low": 200, "deaths_high": 100, "summary": "Inverted range."},
    )
    with pytest.raises(ValidationError):
        finalize(bad, kind="historical")


def test_unknown_era_rejected():
    bad = _draft("https://www.britannica.com/x", era="space-age")
    with pytest.raises(ValidationError):
        finalize(bad, kind="historical")


def test_missing_date_display_rejected():
    bad = _draft("https://www.britannica.com/x")
    del bad["historical"]["date_display"]
    with pytest.raises(ValidationError):
        finalize(bad, kind="historical")


def test_historical_rejects_bad_slug():
    bad = _draft("https://www.britannica.com/x")
    bad["id"] = "Bad_Slug"
    with pytest.raises(ValidationError):
        finalize(bad, kind="historical")


def test_normalization_strips_historical_fields():
    rec = finalize(
        _draft("https://www.britannica.com/x", date_display="  c. 1177 BCE  "),
        kind="historical",
    )
    assert rec["historical"]["date_display"] == "c. 1177 BCE"


def test_finalize_mutates_in_place_no_writes():
    before = copy.deepcopy(_draft("https://www.britannica.com/x"))
    rec = finalize(before, kind="historical")
    assert rec is before
