"""Anthropic client construction and the single, context-free layer call.

`call_layer` always builds a single-turn message with a fresh system prompt — there is
deliberately no parameter for passing prior messages, so layers cannot share context
(ARCHITECTURE.md §5). DryRunClient is a sentinel: layers branch on `is_dry_run(client)` and
take a deterministic local path, exercising the full orchestration for $0.
"""

from __future__ import annotations

import json
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


# --- Usage / cost accounting (real-API path only) --------------------------
# call_layer() appends one record per live model call; the orchestrator resets
# this at the start of a run and prints a cost summary at the end. DryRunClient
# never reaches call_layer, so the dry-run path records nothing.
_USAGE: list[dict] = []


def reset_usage() -> None:
    _USAGE.clear()


def _record_usage(model: str, resp) -> None:
    u = getattr(resp, "usage", None)
    if u is None:
        return
    server = getattr(u, "server_tool_use", None)
    web_searches = getattr(server, "web_search_requests", 0) or 0 if server else 0
    _USAGE.append({
        "model": model,
        "input_tokens": getattr(u, "input_tokens", 0) or 0,
        "output_tokens": getattr(u, "output_tokens", 0) or 0,
        "web_searches": web_searches,
    })


def usage_summary() -> dict:
    """Aggregate recorded usage into per-model totals + estimated USD cost."""
    by_model: dict[str, dict] = {}
    for rec in _USAGE:
        agg = by_model.setdefault(
            rec["model"],
            {"calls": 0, "input_tokens": 0, "output_tokens": 0, "web_searches": 0},
        )
        agg["calls"] += 1
        agg["input_tokens"] += rec["input_tokens"]
        agg["output_tokens"] += rec["output_tokens"]
        agg["web_searches"] += rec["web_searches"]
    total = 0.0
    for model, agg in by_model.items():
        agg["cost_usd"] = round(
            config.estimate_cost(
                model, agg["input_tokens"], agg["output_tokens"], agg["web_searches"]
            ),
            4,
        )
        total += agg["cost_usd"]
    return {"by_model": by_model, "total_cost_usd": round(total, 4)}


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
    resp = client.messages.create(**kwargs)
    _record_usage(model, resp)
    return resp


def first_json(resp) -> dict:
    """Parse the first text block of a structured-output response as JSON."""
    for block in getattr(resp, "content", []):
        if getattr(block, "type", None) == "text":
            return json.loads(block.text)
    raise ValueError("response contained no text block to parse")
