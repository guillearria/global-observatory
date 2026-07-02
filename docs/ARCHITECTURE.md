# World Watch — Architecture

A fact-based watch on the world: a daily **World Pulse** of confirmed major events plus a
weekly-refreshed **Existential Threats** tracker, published as a static page. Every published figure
is grounded in an official, authoritative source. It is explicitly **an aggregation of authoritative
figures, not a forecast.**

## 1. The two content types

| | Existential Threats | World Pulse (events) |
|---|---|---|
| What | Standing risks (supervolcano, pandemic, nuclear war, …) | Dated occurrences (earthquake, outbreak, displacement crisis) |
| Records | `data/threats/*.json` | `data/events/*.json` |
| Schema | `data/schema/threat.schema.json` | `data/schema/event.schema.json` |
| Domain block | `assessment` (probability × severity) | `event` (date, location, status, scale, impact) |
| Sort | severity-dominant | recency-dominant (today outranks last month) |
| Cadence | weekly, via `/refresh-threats` | daily, via `/refresh-events` |
| Publish | human-reviewed **PR** | **auto-publish** straight to `main` (no reviewer in a daily unattended loop) |

Both schemas share `claims[]`, `verification`, `provenance`, `last_updated`, `schema_version`
byte-for-byte — the trust spine is identical. Shared functions (`schema.validate`,
`store.write_record`/`load_all`, `curate.finalize`/`write`/`compute_sort_keys`, `models.index_of`)
take a `kind: "threat"|"event"` parameter, defaulting to `"threat"`.

## 2. Trust model

- **The gate decides, never the drafter.** `pipeline/gate.py:apply_gate` re-checks every claim's
  `source_url` against `SOURCE_ALLOWLIST` (`pipeline/config.py`) — a deterministic Python domain
  match. A claim marked verified but citing a non-allowlisted domain is downgraded to unverified.
- A record publishes only with **≥1 verified claim and 0 disputed claims**; otherwise it is written
  to the kind's quarantine dir (`data/quarantine/`, `data/quarantine-events/`) and rendered by the
  frontend under "Under review", clearly flagged — held back, never presented as confirmed.
- Categorical fields (a threat's severity/probability estimate, an event's status/scale) are
  editorial judgment; the **numeric claims** are what must cite an allowlisted source.
- **Known limit:** the gate verifies that an authoritative source was *cited*, not deep semantic
  entailment that the source supports the claim. The `disputed`/`partial` statuses give reviewers a
  hook; the README states the limit plainly.
- To propose a new authoritative domain, PR an addition to `SOURCE_ALLOWLIST` with a one-line
  justification (see CONTRIBUTING.md).

## 3. Data model — git is the database

One JSON file per record, serialized deterministically (`json.dumps(..., indent=2, sort_keys=True,
ensure_ascii=False)`) so git diffs are meaningful: a re-verify that confirms the same facts diffs
only `retrieved_date` + `provenance`; a changed fact produces a clear, reviewable diff. Stable
`claims[].id` values keep re-verification diffs in place. `CHANGELOG.md` is **generated** by
`pipeline/changelog.py` from `git log` over `data/**` — git history is canonical; the changelog is a
human-readable projection.

Key record fields (see the schema files for the full contract):

- `claims[]` — `{id, text, source_name, source_url, retrieved_date, verification_status}`.
- `verification` — `{status: verified|partial|quarantined|unverified, confidence, notes}` — written
  by the gate.
- `sort_keys` — computed by `curate.compute_sort_keys`: threats `severity_rank*10 +
  probability_rank`; events `recency_rank*10 + impact_rank` (day-ordinal recency, so the rank is
  stable and rebuild-independent).
- `provenance` — append-only `{layer, run_id, at}` history, capped at 20.
- Threat `assessment.probability` carries a categorical `estimate` plus optional published
  `numeric_annual` — no invented precision.

## 4. Curation flow (the $0 path)

The dataset is curated by **Claude Code on a Claude Max subscription** — its own WebSearch/WebFetch,
no API credits. Two slash commands (`.claude/commands/refresh-*.md`) drive it:

```
research (WebSearch/WebFetch against allowlisted sources)
  -> draft JSON (author-supplied fields only)
  -> scripts/author_threat.py | author_event.py        # the gate decides
       = pipeline/curate.finalize: normalize -> apply_gate -> sort_keys -> provenance -> validate
       = writes to the published or quarantine dir by gate result
  -> scripts/validate_data.py && scripts/build_frontend.py && pytest
  -> pipeline/changelog.regenerate()
  -> events: commit + push (a cloud session's push lands on its claude/* branch; the
     publish-events workflow re-validates scope + schema, then merges to main) | threats: open a PR
```

Hand-authoring follows the same path (see CONTRIBUTING.md). There is no other write path — nothing
publishes without passing `finalize`.

## 5. Module map

```
pipeline/
  config.py     paths, SOURCE_ALLOWLIST + allowlisted(), rank tables
  gate.py       apply_gate — the deterministic quarantine gate (imports only config)
  curate.py     finalize/write + _normalize + compute_sort_keys — the whole authoring path
  models.py     deterministic dumps, slugs, run ids, provenance stamp, index_of
  schema.py     jsonschema validation + Python-side range/slug checks
  store.py      atomic per-record JSON store, kind-aware dirs
  frontend.py   aggregate published records -> frontend/data/{threats,events}.json
  changelog.py  regenerate CHANGELOG.md from git history
scripts/        author_threat.py, author_event.py, validate_data.py, build_frontend.py, serve_frontend.py
tests/          gate, curate (both kinds), schema, store, models round-trip
```

## 6. Frontend

Vanilla HTML/CSS/JS, no build step. `app.js` fetches `frontend/data/{events,threats}.json`
(cache-busted, with a localStorage last-known-good fallback) and renders two panes: World Pulse
(flat, recency-sorted) and Existential Threats (grouped by category, severity-sorted). Each card
shows verification badges and an expandable, source-linked claims list. Quarantined records render
under an "Under review" warning banner. Freshness honesty: cached figures are labeled "as of
<claims' retrieved_date>" with a "live at source" link (`event.live_source_url`); a **staleness
banner** appears when `last_updated` exceeds 2 days (events) or 10 days (threats).

## 7. Operations

- **`validate.yml`** — on every PR/push: ruff, pytest, `validate_data.py` (the hard schema gate),
  frontend build.
- **`pages.yml`** — on push to `main` touching `frontend/**`: rebuilds the aggregates and deploys
  `frontend/` to GitHub Pages.
- **`publish-events.yml`** — the auto-publish bridge: when a cloud session pushes a `claude/*`
  branch, it merges to `main` only if the branch touches nothing but events data + the aggregate +
  CHANGELOG and passes schema validation with a byte-exact aggregate. Threats branches are skipped
  (they go through PR review). This enforces the refresh commands' write-scope rule mechanically.
- **`staleness.yml`** — daily scheduled check that fails loudly (GitHub notification) if the
  committed `frontend/data/*.json` goes stale (>2 days events / >10 days threats) — the server-side
  complement to the frontend banner, catching a silently-dead refresh schedule.
- **Refresh schedule** — two Claude Code scheduled cloud agents: daily → `/refresh-events`, weekly →
  `/refresh-threats`.

## 8. History

The project began as a four-stage pipeline of independent Claude **API** calls (Generate → Verify →
Clean-up → Optimize) orchestrated by a daily GitHub Actions cron. That path spent API credits a Max
subscription can't cover, so curation moved to Claude Code and the pipeline was retired; the
deterministic trust gate it pioneered is the part that survived (now `pipeline/gate.py`). The full
blueprint and implementation live in git history — see `docs/ARCHITECTURE.md` and `pipeline/` before
commit "Delete the legacy 4-layer API pipeline".
