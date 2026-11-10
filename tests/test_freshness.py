import importlib.util
import io
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    "check_freshness", Path(__file__).parents[1] / "scripts/check_freshness.py"
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
check_data = module.check_data

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


@pytest.mark.parametrize("report_only,expected", [(False, 1), (True, 0)])
def test_advisory_does_not_hide_stale_records(report_only, expected, capsys, monkeypatch, tmp_path):
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    errors = ["indonesia: refresh age 2.5 days (limit 2)"]
    assert module.report(errors, report_only=report_only) == expected
    output = capsys.readouterr().out
    assert errors[0] in output
    assert "checks passed" not in output
    assert ("::warning::" in output) == report_only
    assert "Freshness: incomplete" in summary.read_text()
    if report_only:
        assert "does not block valid data publication" in summary.read_text()
        assert "remain strict" in summary.read_text()


def test_fresh_report_is_successful(monkeypatch, tmp_path, capsys):
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    assert module.report([]) == 0
    assert "checks passed" in capsys.readouterr().out
    assert "Freshness: passed" in summary.read_text()
    assert "incomplete" not in summary.read_text()


@pytest.mark.parametrize("argv,expected,live", [([], 1, False), (["--live"], 1, True),
                                              (["--report-only"], 0, False)])
def test_cli_strict_by_default_and_live(argv, expected, live, monkeypatch):
    calls = []

    def collect_errors(**kwargs):
        calls.append(kwargs)
        return ["stale ongoing event"]

    monkeypatch.setattr(module, "collect_errors", collect_errors)
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    with pytest.raises(SystemExit) as result:
        module.main(argv)
    assert result.value.code == expected
    assert calls == [{"live": live}]


def write_collections(tmp_path):
    target = tmp_path / "frontend" / "data"
    target.mkdir(parents=True)
    data = {"last_updated": datetime.now(UTC).isoformat(), "published": []}
    for kind in module.LIMITS:
        (target / f"{kind}.json").write_text(json.dumps(data))
    return data


def test_preflight_is_read_only_and_does_not_fetch(monkeypatch, tmp_path):
    write_collections(tmp_path)
    monkeypatch.chdir(tmp_path)
    before = {p: p.read_bytes() for p in tmp_path.rglob("*.json")}

    def forbidden_fetch(*args, **kwargs):
        pytest.fail("Offline preflight must not make network requests")

    monkeypatch.setattr(module, "urlopen", forbidden_fetch)
    assert module.collect_errors() == []
    assert before == {p: p.read_bytes() for p in tmp_path.rglob("*.json")}


def test_live_checks_both_collections_and_detects_mismatch(monkeypatch, tmp_path):
    data = write_collections(tmp_path)
    monkeypatch.chdir(tmp_path)
    calls = []

    def fetch(request, timeout):
        calls.append((request.full_url, timeout))
        deployed = {**data, "published": [], "extra": "mismatch"}
        return io.StringIO(json.dumps(deployed))

    monkeypatch.setattr(module, "urlopen", fetch)
    errors = module.collect_errors(live=True)
    assert len(calls) == 2
    assert errors == [f"{kind}: deployed aggregate differs from checked commit; inspect Pages"
                      for kind in module.LIMITS]


def test_live_fetch_failure_stays_a_failure(monkeypatch, tmp_path):
    write_collections(tmp_path)
    monkeypatch.chdir(tmp_path)

    def fail(*args, **kwargs):
        raise OSError("service unavailable")

    monkeypatch.setattr(module, "urlopen", fail)
    errors = module.collect_errors(live=True)
    assert len(errors) == 2
    assert all("cannot verify deployed data" in error for error in errors)
    assert module.report(errors) == 1


def ongoing(name, stamp):
    return {"id": name, "last_updated": stamp, "event": {"status": "ongoing"}}


def test_review_queue_catches_daily_start_cutoff_gap_without_failing_fresh_data():
    # At 09:00 these records pass, but become stale minutes after a daily run starts.
    now = datetime(2026, 11, 10, 9, tzinfo=UTC)
    data = {"last_updated": now.isoformat(), "published": [
        ongoing("later", "2026-11-08T09:23:00Z"),
        ongoing("earlier", "2026-11-08T09:16:00Z"),
    ]}
    assert check_data("events", data, now) == []
    rows = module.review_queue(data, now, 24)
    assert [row.split(":", 1)[0] for row in rows] == ["earlier", "later"]
    assert "2026-11-10T09:16:00Z" in rows[0]
    assert len(check_data("events", data, now + timedelta(minutes=25))) == 2


def test_review_queue_orders_overdue_first_and_includes_exact_horizon():
    data = {"published": [
        ongoing("tomorrow", "2026-11-03T12:00:00Z"),
        ongoing("later", "2026-11-03T12:00:01Z"),
        ongoing("overdue", "2026-11-01T12:00:00Z"),
        {"id": "resolved", "last_updated": "2020-01-01T00:00:00Z",
         "event": {"status": "resolved"}},
    ]}
    rows = module.review_queue(data, NOW, 24)
    assert [row.split(":", 1)[0] for row in rows] == ["overdue", "tomorrow"]
    assert "(overdue)" in rows[0]
    assert "due within review window" in rows[1]


@pytest.mark.parametrize("stamp", [None, "undefined", "2026-11-04", "2027-01-01T00:00:00Z"])
def test_review_queue_keeps_invalid_dates_visible(stamp):
    rows = module.review_queue({"published": [ongoing("invalid", stamp)]}, NOW, 24)
    assert rows == ["invalid: invalid refresh date; inspect the record"]


def test_review_queue_is_read_only_and_does_not_fetch(monkeypatch, tmp_path, capsys):
    write_collections(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    before = {p: p.read_bytes() for p in tmp_path.rglob("*.json")}
    monkeypatch.setattr(module, "urlopen", lambda *a, **kw: pytest.fail("No network allowed"))
    module.report_review_queue(24)
    assert before == {p: p.read_bytes() for p in tmp_path.rglob("*.json")}
    assert "successful source reads are required" in capsys.readouterr().out


@pytest.mark.parametrize("report_only,expected", [(False, 1), (True, 0)])
def test_review_window_does_not_change_strict_exit_status(report_only, expected, monkeypatch):
    calls = []
    monkeypatch.setattr(module, "collect_errors", lambda **kwargs: ["stale event"])
    monkeypatch.setattr(module, "report_review_queue", calls.append)
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    argv = ["--review-window-hours", "24"] + (["--report-only"] if report_only else [])
    with pytest.raises(SystemExit) as result:
        module.main(argv)
    assert result.value.code == expected
    assert calls == [24]


@pytest.mark.parametrize("hours", ["0", "-1", "invalid"])
def test_review_window_rejects_invalid_duration(hours):
    with pytest.raises(SystemExit) as result:
        module.main(["--review-window-hours", hours])
    assert result.value.code == 2
