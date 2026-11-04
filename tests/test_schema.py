import copy

import jsonschema
import pytest

from pipeline import config, schema, store

SEED = store.load(config.THREATS_DIR / "yellowstone-supervolcano.json")


def test_schema_is_valid_draft_2020_12():
    jsonschema.Draft202012Validator.check_schema(schema.load_schema())


def test_historical_schema_is_valid_draft_2020_12():
    jsonschema.Draft202012Validator.check_schema(schema.load_schema("historical"))


def test_seed_validates():
    schema.validate(copy.deepcopy(SEED))


def test_missing_required_field_rejected():
    bad = copy.deepcopy(SEED)
    del bad["verification"]
    with pytest.raises(schema.ValidationError):
        schema.validate(bad)


def test_unknown_enum_value_rejected():
    bad = copy.deepcopy(SEED)
    bad["category"] = "alien-invasion"
    with pytest.raises(schema.ValidationError):
        schema.validate(bad)


def test_bad_slug_rejected_in_python():
    bad = copy.deepcopy(SEED)
    bad["id"] = "Not A Slug"
    with pytest.raises(schema.ValidationError):
        schema.validate(bad)


def test_rank_out_of_range_rejected_in_python():
    bad = copy.deepcopy(SEED)
    bad["sort_keys"]["severity_rank"] = 9
    with pytest.raises(schema.ValidationError):
        schema.validate(bad)


@pytest.fixture(params=["threat", "event", "historical"])
def dated_record(request):
    paths = {
        "threat": config.THREATS_DIR / "yellowstone-supervolcano.json",
        "event": config.EVENTS_DIR / "china-earthquake-nagqu-2026.json",
        "historical": config.HISTORICAL_DIR / "black-death.json",
    }
    return request.param, store.load(paths[request.param])


@pytest.mark.parametrize("raw", [
    "undefined", "null", "unknown", " ", "2026-02-29", "2026-04-31",
    "0000-01-01", "2026-13-01", "20261102", "2026-W45-1", "2026-1-2",
    "2026-11-02T00:00:00Z", " 2026-11-02", "2026-11-02\n",
    20261102,
])
def test_claim_retrieved_date_rejects_invalid_values(dated_record, raw):
    kind, rec = dated_record
    rec["claims"][0]["retrieved_date"] = raw
    before = copy.deepcopy(rec)
    with pytest.raises(schema.ValidationError, match="retrieved_date"):
        schema.validate(rec, kind)
    assert rec == before  # validation must never rewrite provenance


@pytest.mark.parametrize("raw", ["", "2024-02-29", "2026-11-02"])
def test_claim_retrieved_date_accepts_calendar_date_or_never_sentinel(dated_record, raw):
    kind, rec = dated_record
    rec["claims"][0]["retrieved_date"] = raw
    schema.validate(rec, kind)
    assert rec["claims"][0]["retrieved_date"] == raw


def test_claim_retrieved_date_reports_every_invalid_claim():
    rec = copy.deepcopy(SEED)
    rec["claims"] = [copy.deepcopy(rec["claims"][0]) for _ in range(2)]
    for i, claim in enumerate(rec["claims"]):
        claim["id"] = f"claim-{i + 1}"
        claim["retrieved_date"] = "undefined"
    with pytest.raises(schema.ValidationError) as exc:
        schema.validate(rec)
    assert "claims[0].retrieved_date" in str(exc.value)
    assert "claims[1].retrieved_date" in str(exc.value)


@pytest.mark.parametrize("note", [None, "", " ", 42])
def test_unknown_retrieval_date_requires_explanation(dated_record, note):
    kind, rec = dated_record
    rec["claims"][0]["retrieved_date"] = None
    if note is not None:
        rec["claims"][0]["retrieval_note"] = note
    with pytest.raises(schema.ValidationError, match="retrieval_note"):
        schema.validate(rec, kind)


def test_unknown_retrieval_date_preserves_claim_and_explanation(dated_record):
    kind, rec = dated_record
    claim = rec["claims"][0]
    claim["retrieved_date"] = None
    claim["retrieval_note"] = "Legacy import did not record a retrieval date."
    before = copy.deepcopy(rec)
    schema.validate(rec, kind)
    assert rec == before


def test_missing_retrieved_date_is_not_implicitly_unknown(dated_record):
    kind, rec = dated_record
    del rec["claims"][0]["retrieved_date"]
    with pytest.raises(schema.ValidationError, match="retrieved_date"):
        schema.validate(rec, kind)
