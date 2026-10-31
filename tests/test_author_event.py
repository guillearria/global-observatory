"""World Pulse events run through the same deterministic gate as threats (kind='event')."""

import copy
import json

import pytest

from pipeline.curate import _impact_rank, _recency_rank, finalize
from pipeline.schema import ValidationError


def _draft(source_url, updates=None, **event_overrides):
    event = {
        "occurrence_date": "2026-06-25",
        "location": {"country": "Venezuela", "region": "Near Moron"},
        "status": "ongoing",
        "scale": "M7.5",
        "impact": {"deaths": 12, "displaced": 5000, "summary": "Figures as of 2026-06-30."},
        "live_source_url": "https://earthquake.usgs.gov/earthquakes/eventpage/x",
    }
    event.update(event_overrides)
    draft = {
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
    if updates is not None:
        draft["updates"] = updates
    return draft


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


def test_event_location_accepts_optional_lat_lon():
    # lat/lon were once cut as premature; the World Pulse map is their consumer now.
    # They stay optional — an event with no coordinates simply doesn't appear on the map.
    draft = _draft("https://earthquake.usgs.gov/x")
    draft["event"]["location"]["lat"] = 10.4
    draft["event"]["location"]["lon"] = -68.3
    rec = finalize(draft, kind="event")
    assert rec["event"]["location"]["lat"] == 10.4
    assert rec["event"]["location"]["lon"] == -68.3


def test_event_location_lat_lon_range_checked():
    bad = _draft("https://earthquake.usgs.gov/x")
    bad["event"]["location"]["lat"] = 123.0
    with pytest.raises(ValidationError):
        finalize(bad, kind="event")
    bad = _draft("https://earthquake.usgs.gov/x")
    bad["event"]["location"]["lon"] = -190.0
    with pytest.raises(ValidationError):
        finalize(bad, kind="event")


def test_event_location_still_rejects_unknown_keys():
    # additionalProperties: false stays load-bearing — only lat/lon were added.
    bad = _draft("https://earthquake.usgs.gov/x")
    bad["event"]["location"]["magnitude"] = 7.5
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


# --- updates[] development log ----------------------------------------------

def test_updates_round_trip_through_finalize():
    # Unordered, whitespace-padded, and duplicated entries in; normalized out.
    rec = finalize(_draft("https://earthquake.usgs.gov/x", updates=[
        {"date": "2026-06-26", "text": "  Toll revised to 12. "},
        {"date": "2026-06-28", "text": "Displacement figure doubled."},
        {"date": "2026-06-26", "text": "Toll revised to 12."},
    ]), kind="event")
    assert rec["updates"] == [
        {"date": "2026-06-28", "text": "Displacement figure doubled."},
        {"date": "2026-06-26", "text": "Toll revised to 12."},
    ]


def test_updates_rejects_bad_date():
    with pytest.raises(ValidationError):
        finalize(_draft("https://earthquake.usgs.gov/x",
                        updates=[{"date": "06/26/2026", "text": "Toll revised."}]),
                 kind="event")


def test_updates_entry_cap():
    entries = [{"date": f"2026-06-{d:02d}", "text": f"Development {d}."} for d in range(1, 31)]
    rec = finalize(_draft("https://earthquake.usgs.gov/x", updates=list(entries)), kind="event")
    assert len(rec["updates"]) == 30  # exactly at the cap passes
    entries.append({"date": "2026-07-01", "text": "One too many."})
    with pytest.raises(ValidationError):
        finalize(_draft("https://earthquake.usgs.gov/x", updates=entries), kind="event")


def test_updates_text_cap():
    rec = finalize(_draft("https://earthquake.usgs.gov/x",
                          updates=[{"date": "2026-06-26", "text": "x" * 400}]), kind="event")
    assert len(rec["updates"][0]["text"]) == 400  # exactly at the cap passes
    with pytest.raises(ValidationError):
        finalize(_draft("https://earthquake.usgs.gov/x",
                        updates=[{"date": "2026-06-26", "text": "x" * 401}]), kind="event")


def test_updates_text_subject_to_prose_checks():
    with pytest.raises(ValidationError):
        finalize(_draft("https://earthquake.usgs.gov/x",
                        updates=[{"date": "2026-06-26",
                                  "text": "Re-checked 26 June: no change."}]),
                 kind="event")


def test_updates_rejects_unknown_keys():
    with pytest.raises(ValidationError):
        finalize(_draft("https://earthquake.usgs.gov/x",
                        updates=[{"date": "2026-06-26", "text": "ok", "author": "x"}]),
                 kind="event")


# --- prose discipline --------------------------------------------------------

def test_normalize_strips_event_fields():
    rec = finalize(_draft("https://earthquake.usgs.gov/x",
                          scale="  M7.5 ",
                          impact={"deaths": 12, "displaced": 5000,
                                  "summary": "  Figures as of 2026-06-30.  "},
                          location={"country": "Venezuela", "region": "  Near Moron  "}),
                   kind="event")
    assert rec["event"]["scale"] == "M7.5"
    assert rec["event"]["impact"]["summary"] == "Figures as of 2026-06-30."
    assert rec["event"]["location"]["region"] == "Near Moron"


def test_event_prose_rejects_process_narration():
    bad = _draft("https://earthquake.usgs.gov/x")
    bad["description"] = "Re-checked 8 August 2026: figures unchanged."
    with pytest.raises(ValidationError):
        finalize(bad, kind="event")
    bad = _draft("https://earthquake.usgs.gov/x")
    bad["event"]["impact"]["summary"] = "GDACS shows no newer episode for this event."
    with pytest.raises(ValidationError):
        finalize(bad, kind="event")


def test_event_prose_rejects_allowlisted_mention():
    bad = _draft("https://earthquake.usgs.gov/x")
    bad["event"]["impact"]["summary"] = "No allowlisted source has declared the event resolved."
    with pytest.raises(ValidationError):
        finalize(bad, kind="event")


def test_event_region_capped_and_phrase_checked():
    bad = _draft("https://earthquake.usgs.gov/x",
                 location={"country": "Venezuela", "region": "x" * 201})
    with pytest.raises(ValidationError):
        finalize(bad, kind="event")
    bad = _draft("https://earthquake.usgs.gov/x",
                 location={"country": "Venezuela",
                           "region": "Near Moron (pending any newer GDACS episode)"})
    with pytest.raises(ValidationError):
        finalize(bad, kind="event")


def test_event_prose_length_caps():
    ok = _draft("https://earthquake.usgs.gov/x")
    ok["description"] = "y" * 1200
    assert finalize(ok, kind="event")["verification"]["status"] == "verified"
    bad = _draft("https://earthquake.usgs.gov/x")
    bad["description"] = "y" * 1201
    with pytest.raises(ValidationError):
        finalize(bad, kind="event")


def test_claims_text_exempt_from_prose_checks():
    # Legacy claims kept verbatim through the cleanup carry process prefixes; claim
    # text is never restyled, so the prose checks must not reach it.
    draft = _draft("https://earthquake.usgs.gov/x")
    draft["claims"][0]["text"] = "Re-confirmed by direct fetch on 30 June 2026: 12 deaths."
    rec = finalize(draft, kind="event")
    assert rec["verification"]["status"] == "verified"


# --- updates[] drop guard (October 2026: a full log was trimmed oldest-first, losing milestones)
def _logged(*texts):
    return {"id": "test-event",
            "updates": [{"date": f"2026-06-{i + 10:02d}", "text": t} for i, t in enumerate(texts)]}


def test_dropped_updates_new_record_or_additive_draft_is_empty():
    from pipeline.curate import dropped_updates

    assert dropped_updates(None, _logged("A.")) == []
    prev = _logged("A.", "B.")
    draft = copy.deepcopy(prev)
    draft["updates"].append({"date": "2026-06-30", "text": "C."})
    assert dropped_updates(prev, draft) == []


def test_dropped_updates_matches_on_normalized_text():
    from pipeline.curate import dropped_updates

    prev = _logged("Toll revised to 12.")
    draft = {"updates": [{"date": " 2026-06-10 ", "text": "  toll REVISED to 12. "}]}
    assert dropped_updates(prev, draft) == []  # whitespace/case-only differences are not drops


def test_dropped_updates_lists_removed_and_rewritten_entries_oldest_first():
    from pipeline.curate import dropped_updates

    prev = _logged("Oldest.", "Middle.", "Newest.")
    draft = {"updates": [{"date": "2026-06-12", "text": "Newest, revised."},
                         {"date": "2026-06-11", "text": "Middle."}]}
    assert [u["text"] for u in dropped_updates(prev, draft)] == ["Oldest.", "Newest."]


def _run_author_event(monkeypatch, tmp_path, draft, *flags):
    import importlib.util
    import sys
    from pathlib import Path

    from pipeline import config

    spec = importlib.util.spec_from_file_location(
        "author_event", Path(__file__).resolve().parents[1] / "scripts" / "author_event.py")
    author_event = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(author_event)

    monkeypatch.setattr(config, "EVENTS_DIR", tmp_path / "events")
    monkeypatch.setattr(config, "QUARANTINE_EVENTS_DIR", tmp_path / "quarantine-events")
    path = tmp_path / "draft.json"
    path.write_text(json.dumps(draft), encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["author_event", *flags, str(path)])
    author_event.main()
    return json.loads((tmp_path / "events" / "test-event.json").read_text(encoding="utf-8"))


def test_author_event_refuses_a_draft_that_drops_updates(monkeypatch, tmp_path, capsys):
    url = "https://earthquake.usgs.gov/x"
    first = _draft(url, updates=[{"date": "2026-06-26", "text": "Toll revised to 12."},
                                 {"date": "2026-06-28", "text": "Displacement doubled."}])
    _run_author_event(monkeypatch, tmp_path, first)

    trimmed = _draft(url, updates=[{"date": "2026-06-28", "text": "Displacement doubled."}])
    with pytest.raises(SystemExit) as exc:
        _run_author_event(monkeypatch, tmp_path, copy.deepcopy(trimmed))
    assert "Refusing" in str(exc.value)
    assert "Toll revised to 12." in capsys.readouterr().err
    on_disk = json.loads((tmp_path / "events" / "test-event.json").read_text(encoding="utf-8"))
    assert len(on_disk["updates"]) == 2  # nothing was written

    rec = _run_author_event(monkeypatch, tmp_path, trimmed, "--condense")
    assert [u["text"] for u in rec["updates"]] == ["Displacement doubled."]
