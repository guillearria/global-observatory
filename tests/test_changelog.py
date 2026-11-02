"""changelog.regenerate() must never write from truncated (shallow) history."""

import pytest

from pipeline import changelog, config


def test_regenerate_refuses_a_shallow_clone(monkeypatch, tmp_path):
    target = tmp_path / "CHANGELOG.md"
    target.write_text("untouched", encoding="utf-8")
    monkeypatch.setattr(config, "CHANGELOG_PATH", target)

    def fake_git(*args):
        assert args == ("rev-parse", "--is-shallow-repository"), args  # nothing else may run
        return "true\n"

    monkeypatch.setattr(changelog, "_git", fake_git)
    with pytest.raises(changelog.ShallowCloneError):
        changelog.regenerate()
    assert target.read_text(encoding="utf-8") == "untouched"
