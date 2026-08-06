#!/usr/bin/env python3
"""One-way Telegram push — the only alarm in this repo that leaves GitHub.

Transport only: the caller composes the message, this sends it. Reads TELEGRAM_BOT_TOKEN and
TELEGRAM_CHAT_ID from the environment (Actions secrets in CI); prints a status line and exits 0
on a confirmed send, 1 otherwise.

Why this exists: every other alarm here is a red CI run, and a red CI run only reaches a human
who is subscribed to it. `staleness` failed on 11 consecutive days in July 2026 while the weekly
threats routine sat broken, and nobody saw it — under auto-publish the "last committer" GitHub
notifies is the publisher bot. See docs/BACKLOG.md.

    python3 scripts/notify.py "text"     # send
    echo "text" | python3 scripts/notify.py -
    python3 scripts/notify.py            # print config status, send nothing
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

API = "https://api.telegram.org/bot{token}/sendMessage"
TIMEOUT_S = 10
MAX_LEN = 3900  # Telegram's hard limit is 4096; leave room for the truncation marker
TRUNC_MARK = "\n… truncated"


def configured() -> bool:
    return bool(os.getenv("TELEGRAM_BOT_TOKEN") and os.getenv("TELEGRAM_CHAT_ID"))


def _post(payload: dict) -> bool:
    req = urllib.request.Request(
        API.format(token=os.environ["TELEGRAM_BOT_TOKEN"]),
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
        return bool(json.load(resp).get("ok"))


def send(text: str) -> bool:
    """POST one message. True only when Telegram confirms the send."""
    if not configured():
        print("notify: skipped — TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID unset")
        return False
    if len(text) > MAX_LEN:
        text = text[:MAX_LEN].rsplit("\n", 1)[0] + TRUNC_MARK
    payload = {"chat_id": os.environ["TELEGRAM_CHAT_ID"], "text": text}
    # Deliberately no retry. A timeout or connection error is AMBIGUOUS — the message may have
    # been delivered and only the response lost, so retrying double-posts. One lost alarm beats
    # two copies of every alarm; the daily staleness run re-sends tomorrow anyway.
    try:
        if _post(payload):
            return True
        print("notify: telegram rejected the message")
    except urllib.error.HTTPError as e:
        print(f"notify: telegram returned HTTP {e.code}")
    except Exception as e:  # noqa: BLE001 — transport must never raise into the caller
        print(f"notify: send failed, not retrying (ambiguous delivery) ({e})")
    return False


def main() -> None:
    argv = sys.argv[1:]
    if not argv:
        print(f"notify: {'CONFIGURED' if configured() else 'NOT configured'} "
              f"(needs TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID)")
        return
    text = sys.stdin.read() if argv == ["-"] else " ".join(argv)
    text = text.strip()
    if not text:
        print("notify: refusing to send an empty message")
        sys.exit(1)
    sys.exit(0 if send(text) else 1)


if __name__ == "__main__":
    main()
