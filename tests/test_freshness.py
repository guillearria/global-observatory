from datetime import UTC, datetime

from scripts.check_freshness import check_data

NOW = datetime(2026, 11, 4, 12, tzinfo=UTC)


def test_one_fresh_record_cannot_mask_stale_ongoing_event():
    data = {"last_updated": "2026-11-04T09:00:00Z", "published": [
        {"id": "old", "last_updated": "2026-10-01T09:00:00Z", "event": {"status": "ongoing"}},
        {"id": "done", "last_updated": "2026-01-01T09:00:00Z", "event": {"status": "resolved"}},
    ]}
    errors = check_data("events", data, NOW)
    assert len(errors) == 1
    assert "old" in errors[0]


def test_invalid_dates_and_future_dates_fail():
    for stamp in (None, "undefined", "2026-11-04", "2027-01-01T00:00:00Z"):
        assert check_data("threats", {"last_updated": stamp, "published": []}, NOW)


def test_weekly_threat_cadence_is_not_a_daily_requirement():
    assert not check_data("threats", {"last_updated": "2026-11-02T10:21:56Z"}, NOW)
