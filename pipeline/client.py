"""Anthropic client construction and the single, context-free layer call.

`call_layer` always builds a single-turn message with a fresh system prompt — there is
deliberately no parameter for passing prior messages, so layers cannot share context
(ARCHITECTURE.md §5). DryRunClient is a sentinel: layers branch on `is_dry_run(client)` and
take a deterministic local path, exercising the full orchestration for $0.
"""

from __future__ import annotations

import os

from . import config


class DryRunClient:
    """Sentinel client used by --dry-run or when ANTHROPIC_API_KEY is unset."""

    is_dry_run = True


def build_client(dry_run: bool = False):
    if dry_run or not os.environ.get("ANTHROPIC_API_KEY"):
        return DryRunClient()
    import anthropic

    return anthropic.Anthropic()


def is_dry_run(client) -> bool:
    return getattr(client, "is_dry_run", False)


def thinking_for(model: str) -> dict | None:
    """Per-model thinking config (Correction #1). None => omit the parameter."""
    if model in config.NO_ADAPTIVE_THINKING:
        return None
    return {"type": "adaptive"}


def call_layer(client, *, model, system, user_content, effort=None, fmt=None, tools=None):
    """One independent, single-turn model call. Real-API path only.

    output_config carries effort and/or the structured-output format. Note the architecture's
    critical constraint: web-search citations and output_config.format cannot coexist (400), so
    the Verify layer never passes both `tools` and `fmt` in the same call.
    """
    output_config: dict = {}
    if effort:
        output_config["effort"] = effort
    if fmt:
        output_config["format"] = fmt

    kwargs: dict = dict(
        model=model,
        max_tokens=config.MAX_TOKENS,
        system=system,
        messages=[{"role": "user", "content": user_content}],
    )
    thinking = thinking_for(model)
    if thinking:
        kwargs["thinking"] = thinking
    if output_config:
        kwargs["output_config"] = output_config
    if tools:
        kwargs["tools"] = tools
    return client.messages.create(**kwargs)
