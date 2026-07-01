# Contributing

This project is a fact-based watch on the world: a daily **World Pulse** of confirmed major events
plus a weekly-refreshed **Existential Threats** tracker. Read
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) first — it is the source of truth for the design.

## The schema contract

Every record is one JSON file — threats at `data/threats/<slug>.json` (validated against
`data/schema/threat.schema.json`), events at `data/events/<slug>.json` (validated against
`data/schema/event.schema.json`). Both schemas share `claims[]`, `verification`, `provenance`,
`last_updated`, `schema_version` byte-for-byte; only the domain block differs (`assessment` for a
standing risk vs. `event` for a dated occurrence) — see `pipeline/schema.py`'s `kind` parameter, which
threads through every shared function (`validate`, `store.write_record`, `optimize.compute_sort_keys`,
`curate.finalize`/`write`) with `kind="threat"` as the default so the original threat path is
untouched. The serialized form is deterministic — `json.dumps(..., indent=2, sort_keys=True,
ensure_ascii=False)` — so git diffs are meaningful and "git history is the changelog" holds. Do not
hand-format these files; let the pipeline's `pipeline.store` write them.

## The layer rules (enforced by Python guards, not convention)

The pipeline runs four **independent** model calls that share no context. Each has a strict remit:

- **Generate** proposes threats and text; every claim it emits is `unverified`.
- **Verify** is the only layer permitted to introduce a `source_url`. It grounds claims against the
  source allowlist and runs the deterministic quarantine gate.
- **Clean-up** does mechanical normalization only — no factual changes.
- **Optimize** may rewrite presentation text and compute `sort_keys`, but **must not** touch
  `claims` text or `source_url`s. A guard asserts claims are byte-identical pre/post and reverts drift.

## Curating with Claude Code (no API spend)

The primary way to refresh the dataset is **Claude Code on a Claude Max subscription** — it spends
no Anthropic API credits. In a Claude Code session run:

```
/refresh-events                            # World Pulse — daily cadence, auto-published, no PR
/refresh-threats <optional list of threats>  # Existential Threats — weekly cadence, opens a PR
```

`/refresh-events` researches confirmed major world events with web search, drafts cited claims, runs
them through the deterministic gate, rebuilds the frontend, and **commits + pushes directly** — there's
no human in a daily unattended loop, so auto-publish via the trust gate is the explicit design (see
[`.claude/commands/refresh-events.md`](.claude/commands/refresh-events.md)). `/refresh-threats` does
the same for standing threats but opens a PR instead, since it's weekly and human-reviewed (see
[`.claude/commands/refresh-threats.md`](.claude/commands/refresh-threats.md)).

**Setting up the actual schedule** (the one piece that can't be done from inside a Claude Code
session) is a Claude Code on the web scheduled trigger, configured in the dashboard — see the top of
[`docs/BACKLOG.md`](docs/BACKLOG.md) for the exact prompts.

## Adding a threat or event by hand

Draft the record minus the computed fields (`verification`, `sort_keys`, `provenance`,
`last_updated`) and finalize it through the same deterministic gate the pipeline uses — the allowlist
decides verified vs quarantined, not you:

1. Write the draft (slug matches `^[a-z0-9-]+$` and the filename), with each claim citing a real
   `source_url` on an allowlisted domain (see `SOURCE_ALLOWLIST` in `pipeline/config.py`).
2. Run `python scripts/author_threat.py draft.json` (writes to `data/threats/` or `data/quarantine/`)
   or `python scripts/author_event.py draft.json` (writes to `data/events/` or
   `data/quarantine-events/`) — it applies the gate, computes `sort_keys`, stamps provenance,
   validates, and writes.
3. Run `python scripts/validate_data.py` (must exit 0) and `python scripts/build_frontend.py`.
4. For a threat, open a PR — CI re-runs schema validation + tests + the frontend build. For an event,
   commit and push directly (see above for why).

## The source allowlist

Claims are only considered `verified` when their citation resolves to a domain on the allowlist in
`pipeline/config.py` — USGS, WHO, IPCC, NASA/CNEOS, IAEA, CDC, NOAA, UN, GDACS, ReliefWeb, IMF, …. To
propose a new authoritative source, open a PR that adds the domain to `SOURCE_ALLOWLIST` with a
one-line justification for why it is authoritative for its category.

## Local development

```sh
pip install -e ".[dev]"
python -m pipeline.run --dry-run     # full pipeline, fixtures, $0
pytest
python scripts/validate_data.py
python scripts/serve_frontend.py     # preview at localhost:8000
```
