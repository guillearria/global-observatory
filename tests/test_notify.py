"""The Telegram transport must never raise into its caller, and must never double-post.

`scripts/` is not a package (the scripts are invoked as `python scripts/…`), so the module is
loaded by path rather than imported.
"""

import importlib.util
import urllib.error
from pathlib import Path

import pytest

_SPEC = importlib.util.spec_from_file_location(
    "notify", Path(__file__).resolve().parent.parent / "scripts" / "notify.py"
)
notify = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(notify)


@pytest.fixture
def armed(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "test-chat")


def test_unconfigured_is_a_skip_not_a_crash(monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    assert notify.configured() is False
    assert notify.send("anything") is False


def test_half_configured_still_counts_as_unconfigured(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    assert notify.configured() is False


def test_send_posts_chat_id_and_text(armed, monkeypatch):
    seen = {}

    def fake_post(payload):
        seen.update(payload)
        return True

    monkeypatch.setattr(notify, "_post", fake_post)
    assert notify.send("hello") is True
    assert seen == {"chat_id": "test-chat", "text": "hello"}


def test_long_message_is_truncated_at_a_newline(armed, monkeypatch):
    sent = {}
    monkeypatch.setattr(notify, "_post", lambda p: sent.update(p) or True)
    notify.send("\n".join(["a line"] * 2000))
    assert len(sent["text"]) <= notify.MAX_LEN + len(notify.TRUNC_MARK)
    assert sent["text"].endswith(notify.TRUNC_MARK)


@pytest.mark.parametrize(
    "boom",
    [
        TimeoutError("timed out"),
        urllib.error.URLError("connection reset"),
        urllib.error.HTTPError("u", 500, "server error", {}, None),
        ValueError("garbage response"),
    ],
)
def test_transport_errors_return_false_instead_of_raising(armed, monkeypatch, boom):
    def fake_post(_payload):
        raise boom

    monkeypatch.setattr(notify, "_post", fake_post)
    assert notify.send("hello") is False


def test_ambiguous_failure_is_not_retried(armed, monkeypatch):
    """A timeout may mean 'delivered, response lost'. Retrying there double-posts."""
    calls = []

    def fake_post(_payload):
        calls.append(1)
        raise TimeoutError("timed out")

    monkeypatch.setattr(notify, "_post", fake_post)
    notify.send("hello")
    assert len(calls) == 1


def test_rejected_message_is_not_retried(armed, monkeypatch):
    calls = []
    monkeypatch.setattr(notify, "_post", lambda p: calls.append(1) or False)
    assert notify.send("hello") is False
    assert len(calls) == 1
