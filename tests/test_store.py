from pipeline import config, store


def test_path_mapping():
    assert store.path_for("nuclear-war").name == "nuclear-war.json"
    assert store.path_for("nuclear-war").parent.name == "threats"
    assert store.quarantine_path_for("x").parent.name == "quarantine"


def test_atomic_write_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "THREATS_DIR", tmp_path / "threats")
    rec = {"id": "demo-threat", "name": "Demo"}

    path = store.write_record(rec)
    assert path.exists()
    assert path.name == "demo-threat.json"
    # No temp files left behind by the atomic write.
    assert not list((tmp_path / "threats").glob("*.tmp"))
    assert store.load(path) == rec


def test_load_all_keys_by_slug(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "THREATS_DIR", tmp_path / "threats")
    store.write_record({"id": "a-threat", "name": "A"})
    store.write_record({"id": "b-threat", "name": "B"})
    loaded = store.load_all()
    assert set(loaded) == {"a-threat", "b-threat"}
    assert loaded["a-threat"]["name"] == "A"


def test_quarantine_write_targets_quarantine_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "QUARANTINE_DIR", tmp_path / "quarantine")
    path = store.write_record({"id": "bad", "name": "Bad"}, quarantine=True)
    assert path.parent == tmp_path / "quarantine"
    assert path.exists()


# --- Event-kind mirrors: guard the regression already hit once (a frozen dict of
# paths in dirs_for broke monkeypatch isolation until fixed with lambdas). ---

def test_path_mapping_events():
    assert store.path_for("earthquake", kind="event").parent.name == "events"
    assert store.quarantine_path_for("x", kind="event").parent.name == "quarantine-events"


def test_atomic_write_roundtrip_events(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "EVENTS_DIR", tmp_path / "events")
    rec = {"id": "demo-event", "name": "Demo"}

    path = store.write_record(rec, kind="event")
    assert path.exists()
    assert path.parent == tmp_path / "events"
    assert store.load(path) == rec


def test_load_all_keys_by_slug_events(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "EVENTS_DIR", tmp_path / "events")
    store.write_record({"id": "a-event", "name": "A"}, kind="event")
    store.write_record({"id": "b-event", "name": "B"}, kind="event")
    loaded = store.load_all(kind="event")
    assert set(loaded) == {"a-event", "b-event"}
    assert loaded["a-event"]["name"] == "A"


def test_quarantine_write_targets_quarantine_events_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "QUARANTINE_EVENTS_DIR", tmp_path / "quarantine-events")
    path = store.write_record({"id": "bad-event", "name": "Bad"}, quarantine=True, kind="event")
    assert path.parent == tmp_path / "quarantine-events"
    assert path.exists()


def test_writing_one_kind_does_not_touch_the_other(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "THREATS_DIR", tmp_path / "threats")
    monkeypatch.setattr(config, "EVENTS_DIR", tmp_path / "events")
    monkeypatch.setattr(config, "HISTORICAL_DIR", tmp_path / "historical")
    store.write_record({"id": "isolated-threat", "name": "T"}, kind="threat")
    store.write_record({"id": "isolated-event", "name": "E"}, kind="event")
    store.write_record({"id": "isolated-historical", "name": "H"}, kind="historical")
    assert set(store.load_all(kind="threat")) == {"isolated-threat"}
    assert set(store.load_all(kind="event")) == {"isolated-event"}
    assert set(store.load_all(kind="historical")) == {"isolated-historical"}
    assert not (tmp_path / "events" / "isolated-threat.json").exists()
    assert not (tmp_path / "threats" / "isolated-event.json").exists()
    assert not (tmp_path / "historical" / "isolated-event.json").exists()


# --- Historical-kind mirrors: same lambda-pattern guard as the event mirrors. ---

def test_path_mapping_historical():
    assert store.path_for("black-death", kind="historical").parent.name == "historical"
    assert store.quarantine_path_for("x", kind="historical").parent.name == "quarantine-historical"


def test_atomic_write_roundtrip_historical(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "HISTORICAL_DIR", tmp_path / "historical")
    rec = {"id": "demo-historical", "name": "Demo"}

    path = store.write_record(rec, kind="historical")
    assert path.exists()
    assert path.parent == tmp_path / "historical"
    assert store.load(path) == rec


def test_quarantine_write_targets_quarantine_historical_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "QUARANTINE_HISTORICAL_DIR", tmp_path / "quarantine-historical")
    path = store.write_record(
        {"id": "bad-historical", "name": "Bad"}, quarantine=True, kind="historical"
    )
    assert path.parent == tmp_path / "quarantine-historical"
    assert path.exists()
