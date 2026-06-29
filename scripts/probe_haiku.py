#!/usr/bin/env python3
"""Correction #1 probe: does claude-haiku-4-5 accept thinking={"type":"adaptive"}?

Run once with a real ANTHROPIC_API_KEY. If it 400s, the pipeline already omits thinking for Haiku
(pipeline.config.NO_ADAPTIVE_THINKING), so no change is needed; this just confirms the assumption.
"""

import os
import sys

from pipeline import config


def main() -> None:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("set ANTHROPIC_API_KEY to run this probe")
        sys.exit(2)
    import anthropic

    client = anthropic.Anthropic()
    try:
        client.messages.create(
            model=config.MODEL_CLEANUP,
            max_tokens=16,
            thinking={"type": "adaptive"},
            messages=[{"role": "user", "content": "ok"}],
        )
        print(f"{config.MODEL_CLEANUP} ACCEPTS adaptive thinking — "
              "you may remove it from config.NO_ADAPTIVE_THINKING")
    except anthropic.BadRequestError as e:
        print(f"{config.MODEL_CLEANUP} REJECTS adaptive thinking (expected): {e}")
        print("pipeline already omits thinking for this model — no change needed")


if __name__ == "__main__":
    main()
