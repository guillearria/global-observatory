# Contributing

This project is a fact-based observatory of the world: a daily **World Pulse** of confirmed major
events, a weekly-refreshed **Existential Threats** tracker, and an ad-hoc-curated **Historical
Archive** reaching back to the dawn of civilization. Read
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) first — it is the source of truth for the design.

## The schema contract

Every record is one JSON file — threats at `data/threats/<slug>.json` (validated against
`data/schema/threat.schema.json`), events at `data/events/<slug>.json` (validated against
`data/schema/event.schema.json`), historical records at `data/historical/<slug>.json` (validated
against `data/schema/historical.schema.json`). All three schemas share `claims[]`, `verification`,
`provenance`, `last_updated`, `schema_version` byte-for-byte; only the domain block differs
(`assessment` for a standing risk, `event` for a dated occurrence, `historical` for an archived
event with BCE-capable chronology) — see `pipeline/schema.py`'s `kind` parameter, which
threads through every shared function (`validate`, `store.write_record`, `curate.compute_sort_keys`,
`curate.finalize`/`write`) with `kind="threat"` as the default so the original threat path is
untouched. The serialized form is deterministic — `json.dumps(..., indent=2, sort_keys=True,
ensure_ascii=False)` — so git diffs are meaningful and "git history is the changelog" holds. Do not
hand-format these files; let `pipeline.store` write them.

## Curating with Claude Code (no API spend)

The primary way to refresh the dataset is **Claude Code on a Claude Max subscription** — it spends
no Anthropic API credits. In a Claude Code session run:

```
/refresh-events                            # World Pulse — daily cadence
/refresh-threats <optional list of threats>  # Existential Threats — weekly cadence
/refresh-history <optional list of events>   # Historical Archive — ad hoc
```

Each command researches its subject with web search, drafts cited claims, runs them through the
deterministic gate, rebuilds the frontend, and **auto-publishes with no PR**. In a cloud session the
push lands on a `claude/*` branch and the `publish` workflow re-validates it — schema, trust gate,
and aggregates that must reproduce byte-for-byte from the records — before merging into `main`.

There is no review queue by design. The gate is the verification layer: a reviewer who has to
approve every factual update is a reviewer who eventually stops, and the data goes stale behind
them. See [`.claude/commands/refresh-events.md`](.claude/commands/refresh-events.md),
[`.claude/commands/refresh-threats.md`](.claude/commands/refresh-threats.md), and
[`.claude/commands/refresh-history.md`](.claude/commands/refresh-history.md).

**The actual schedule** is two Claude Code scheduled cloud agents (daily → `/refresh-events`,
weekly → `/refresh-threats`) — see the top of [`docs/BACKLOG.md`](docs/BACKLOG.md) for the exact
routine prompts.

## Adding a record by hand

Draft the record minus the computed fields (`verification`, `sort_keys`, `provenance`,
`last_updated`) and finalize it through the same deterministic gate the refresh commands use — the
allowlist decides verified vs quarantined, not you:

1. Write the draft (slug matches `^[a-z0-9-]+$` and the filename), with each claim citing a real
   `source_url` on an allowlisted domain (see `data/source-allowlist.json`).
2. Run `python scripts/author_threat.py draft.json` (writes to `data/threats/` or `data/quarantine/`),
   `python scripts/author_event.py draft.json` (writes to `data/events/` or
   `data/quarantine-events/`), or `python scripts/author_historical.py draft.json` (writes to
   `data/historical/` or `data/quarantine-historical/`) — it applies the gate, computes `sort_keys`,
   stamps provenance, validates, and writes.
3. Run `python scripts/validate_data.py` (must exit 0) and `python scripts/build_frontend.py`.
4. Commit and push. On a `claude/*` branch the `publish` workflow re-validates and merges it; from
   a local clone you can push to `main` directly — `validate` re-runs schema validation + tests +
   the frontend build either way.

## The source allowlist

Claims are only considered `verified` when their citation resolves to a domain on the allowlist in
`pipeline/config.py` — USGS, WHO, IPCC, NASA/CNEOS, IAEA, CDC, NOAA, UN, GDACS, ReliefWeb, IMF, …,
plus a scholarly/reference tier for the Historical Archive (Britannica, Smithsonian, Library of
Congress, national archives and museums, Our World in Data, university presses; deliberately no
Wikipedia). To propose a new authoritative source, open a PR that adds the domain to
`SOURCE_ALLOWLIST` with a one-line justification for why it is authoritative for its category.

## Local development

```sh
pip install -e ".[dev]"
pytest
python scripts/validate_data.py
python scripts/serve_frontend.py     # preview at localhost:8000
```
