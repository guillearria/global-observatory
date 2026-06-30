"""Cost estimation + live-usage accounting (Stage 2 instrumentation)."""

from types import SimpleNamespace

from pipeline import client, config


def test_estimate_cost_known_model():
    # 1M input + 1M output on Opus 4.8 = $5 + $25 = $30; plus 2 searches @ $10/1k.
    cost = config.estimate_cost("claude-opus-4-8", 1_000_000, 1_000_000, web_searches=2)
    assert cost == 30.0 + 2 / 1_000 * 10.0


def test_estimate_cost_unknown_model_is_zero():
    assert config.estimate_cost("some-unlisted-model", 1_000_000, 1_000_000) == 0.0


def _fake_resp(input_tokens, output_tokens, searches=0):
    server = SimpleNamespace(web_search_requests=searches)
    usage = SimpleNamespace(
        input_tokens=input_tokens, output_tokens=output_tokens, server_tool_use=server
    )
    return SimpleNamespace(usage=usage)


def test_usage_summary_aggregates_and_costs():
    client.reset_usage()
    client._record_usage("claude-opus-4-8", _fake_resp(1_000_000, 0, searches=1))
    client._record_usage("claude-opus-4-8", _fake_resp(0, 1_000_000))
    client._record_usage("claude-haiku-4-5", _fake_resp(1_000_000, 1_000_000))

    summary = client.usage_summary()
    opus = summary["by_model"]["claude-opus-4-8"]
    assert opus["calls"] == 2
    assert opus["input_tokens"] == 1_000_000 and opus["output_tokens"] == 1_000_000
    assert opus["web_searches"] == 1
    # $5 in + $25 out + 1 search @ $10/1k = $30.01
    assert opus["cost_usd"] == 30.01
    # Haiku: $1 in + $5 out = $6
    assert summary["by_model"]["claude-haiku-4-5"]["cost_usd"] == 6.0
    assert summary["total_cost_usd"] == 36.01


def test_reset_usage_clears():
    client.reset_usage()
    client._record_usage("claude-opus-4-8", _fake_resp(1_000_000, 0))
    client.reset_usage()
    assert client.usage_summary() == {"by_model": {}, "total_cost_usd": 0.0}
