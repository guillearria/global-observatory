"""Telegram is manual-only, and its self-test is exercised without network access."""

import json
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

WORKFLOW = Path(__file__).parents[1] / ".github/workflows/notify.yml"


def test_notify_has_only_an_explicit_manual_trigger():
    workflow = WORKFLOW.read_text()
    triggers = workflow.split("\non:\n", 1)[1].split("\npermissions:", 1)[0]
    assert triggers.strip() == "workflow_dispatch: {}"
    assert "if: github.event_name == 'workflow_dispatch'" in workflow
    assert "workflow_run" not in workflow
    assert "permissions:\n  contents: read\njobs:" in workflow
    assert "TELEGRAM_BOT_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}" in workflow
    assert "TELEGRAM_CHAT_ID: ${{ secrets.TELEGRAM_CHAT_ID }}" in workflow


@pytest.fixture
def run_self_test(tmp_path):
    # Execute the actual workflow shell with a fake python3. A restricted PATH and
    # isolated cwd prevent this regression test from reaching the real transport.
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    stub = bin_dir / "python3"
    stub.write_text(
        f"#!{sys.executable}\n"
        "import json, os, pathlib, sys\n"
        "pathlib.Path(os.environ['CAPTURE']).write_text(json.dumps({\n"
        "    'argv': sys.argv[1:], 'message': sys.stdin.read(),\n"
        "    'token': os.environ['TELEGRAM_BOT_TOKEN'],\n"
        "    'chat': os.environ['TELEGRAM_CHAT_ID'],\n"
        "}))\n"
        "sys.exit(int(os.environ['TRANSPORT_EXIT']))\n"
    )
    stub.chmod(0o755)
    capture = tmp_path / "capture.json"
    script = textwrap.dedent(WORKFLOW.read_text().split("        run: |\n", 1)[1])

    def run(token="", chat="", transport_exit=0):
        result = subprocess.run(
            ["/bin/bash", "--noprofile", "--norc", "-e", "-o", "pipefail", "-c", script],
            cwd=tmp_path,
            env={
                "PATH": str(bin_dir),
                "TELEGRAM_BOT_TOKEN": token,
                "TELEGRAM_CHAT_ID": chat,
                "RUN_URL": "https://github.com/example/repo/actions/runs/123",
                "CAPTURE": str(capture),
                "TRANSPORT_EXIT": str(transport_exit),
            },
            text=True,
            capture_output=True,
            check=False,
        )
        call = json.loads(capture.read_text()) if capture.exists() else None
        return result, call

    return run


@pytest.mark.parametrize("token,chat", [("", ""), ("test-token", ""), ("", "test-chat")])
def test_self_test_missing_credentials_fails_before_transport(run_self_test, token, chat):
    result, call = run_self_test(token, chat)
    assert result.returncode == 1
    assert "Nothing was sent" in result.stdout
    assert call is None


@pytest.mark.parametrize("transport_exit", [0, 1, 7])
def test_self_test_message_is_truthful_and_propagates_transport_exit(run_self_test, transport_exit):
    result, call = run_self_test("test-token", "test-chat", transport_exit)
    assert result.returncode == transport_exit
    assert call["argv"] == ["scripts/notify.py", "-"]
    assert call["token"] == "test-token"
    assert call["chat"] == "test-chat"
    assert "manual Telegram self-test" in call["message"]
    assert "Automatic Telegram failure alerts are disabled" in call["message"]
    assert "GitHub Actions failure emails depend on your notification settings" in call["message"]
    assert "https://github.com/example/repo/actions/runs/123" in call["message"]
    assert "alarm is armed" not in call["message"]
