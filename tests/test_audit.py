"""The audit layer must independently re-derive trust fields — a record whose gate
verdict, claim statuses, sort keys, or directory placement were edited after the
write-time gate ran has to fail, and an untampered record has to pass."""

from pipeline.audit import audit_record
from pipeline.curate import finalize


def _record(source_url="https://www.usgs.gov/x"):
    return finalize({
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
    })


def test_untampered_record_is_clean():
    assert audit_record(_record()) == []


def test_untampered_quarantined_record_is_clean():
    rec = _record("https://blog.example.com/post")  # gate quarantines it
    assert rec["verification"]["status"] == "quarantined"
    assert audit_record(rec, quarantined=True) == []


def test_swapped_source_url_is_caught():
    # Claim URL edited to a non-allowlisted domain after the gate marked it verified.
    rec = _record()
    rec["claims"][0]["source_url"] = "https://blog.example.com/post"
    msgs = audit_record(rec)
    assert any("verification_status" in m for m in msgs)
    assert any(m.startswith("verification:") for m in msgs)


def test_upgraded_verdict_is_caught():
    rec = _record()
    rec["verification"]["confidence"] = "low"
    assert any(m.startswith("verification:") for m in audit_record(rec))


def test_inflated_sort_keys_are_caught():
    rec = _record()
    rec["sort_keys"]["severity_rank"] = 4
    assert any(m.startswith("sort_keys:") for m in audit_record(rec))


def test_quarantined_record_in_published_dir_is_caught():
    rec = _record("https://blog.example.com/post")
    assert any(m.startswith("placement:") for m in audit_record(rec, quarantined=False))


def test_published_record_in_quarantine_dir_is_caught():
    rec = _record()
    assert any(m.startswith("placement:") for m in audit_record(rec, quarantined=True))


def test_audit_does_not_mutate_the_record():
    rec = _record()
    rec["claims"][0]["source_url"] = "https://blog.example.com/post"
    before = str(rec)
    audit_record(rec)
    assert str(rec) == before  # re-gating happens on a copy
