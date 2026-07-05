# Global Observatory — Architecture

A fact-based observatory of the world: a daily **World Pulse** of confirmed major events (with a
world map), a weekly-refreshed **Existential Threats** tracker, and an ad-hoc-curated **Historical
Archive** reaching back to the dawn of civilization — published as a static page. Every published
figure is grounded in an official, authoritative source. It is explicitly **an aggregation of
authoritative figures, not a forecast.**

## 1. The three content types

| | Existential Threats | World Pulse (events) | Historical Archive |
|---|---|---|---|
| What | Standing risks (supervolcano, pandemic, nuclear war, …) | Dated occurrences (earthquake, outbreak, displacement crisis) | Major past events (Black Death, Tambora, 1918 flu, …) |
| Records | `data/threats/*.json` | `data/events/*.json` | `data/historical/*.json` |
| Schema | `data/schema/threat.schema.json` | `data/schema/event.schema.json` | `data/schema/historical.schema.json` |
| Domain block | `assessment` (probability × severity) | `event` (date, location, status, scale, impact) | `historical` (BCE-capable chronology, era, estimate-range impact) |
| Sort | severity-dominant | recency-dominant (today outranks last month) | chronological (oldest first, grouped by era) |
| Cadence | weekly, via `/refresh-threats` | daily, via `/refresh-events` | ad hoc, via `/refresh-history` |
| Publish | human-reviewed **PR** | **auto-publish** straight to `main` (no reviewer in a daily unattended loop) | human-reviewed **PR** |
| Staleness | banner + workflow, >10 days | banner + workflow, >2 days | **exempt** — an archive cannot go stale |

All three schemas share `claims[]`, `verification`, `provenance`, `last_updated`, `schema_version`
byte-for-byte — the trust spine is identical. Shared functions (`schema.validate`,
`store.write_record`/`load_all`, `curate.finalize`/`write`/`compute_sort_keys`, `models.index_of`)
take a `kind: "threat"|"event"|"historical"` parameter, defaulting to `"threat"`.

**Adding a kind** is a settled recipe: config paths + rank tables → `store._KIND_DIRS` (keep the
lambda pattern) → `schema._SCHEMA_PATHS` + a range-check function → `curate.compute_sort_keys`
branch + `_normalize` field stripping → `frontend.build_*` aggregate → author script +
`validate_data.py`/`build_frontend.py` coverage → `changelog` dirs → tests mirroring the existing
kind tests.

## 2. Trust model

- **The gate decides, never the drafter.** `pipeline/gate.py:apply_gate` re-checks every claim's
  `source_url` against `SOURCE_ALLOWLIST` (`pipeline/config.py`) — a deterministic Python domain
  match. A claim marked verified but citing a non-allowlisted domain is downgraded to unverified.
- The allowlist has informal tiers: official/intergovernmental agencies (USGS, WHO, UN, …),
  event-feed services (GDACS, ReliefWeb), and a scholarly/reference tier for the Historical Archive
  (Britannica, Smithsonian, national archives/museums, Our World in Data, university presses —
  deliberately no Wikipedia). One list, one gate: every kind passes the same check.
- A record publishes only with **≥1 verified claim and 0 disputed claims**; otherwise it is written
  to the kind's quarantine dir (`data/quarantine/`, `data/quarantine-events/`,
  `data/quarantine-historical/`) and rendered by the frontend under "Under review", clearly
  flagged — held back, never presented as confirmed.
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
  stable and rebuild-independent); historical `chronology_rank*10 + impact_rank`.
- `provenance` — append-only `{layer, run_id, at}` history, capped at 20.
- Threat `assessment.probability` carries a categorical `estimate` plus optional published
  `numeric_annual` — no invented precision.
- Event `event.location` carries optional `lat`/`lon` (WGS84 decimal degrees) — the World Pulse
  map's data; events without coordinates simply get no marker.
- Historical chronology is **signed astronomical years** (`year_start`/`year_end`: 0 = 1 BCE,
  -2999 = 3000 BCE) because `date.toordinal` cannot represent BCE;
  `chronology_rank = year_start + 10000` keeps ranks positive back to 9999 BCE. Historical impact
  is an **estimate range** (`deaths_low`/`deaths_high`, quoted as the source states it; the 1–5
  `impact_rank` bands on the midpoint) — ancient tolls are ranges, not counts.

## 4. Curation flow (the $0 path)

The dataset is curated by **Claude Code on a Claude Max subscription** — its own WebSearch/WebFetch,
no API credits. Three slash commands (`.claude/commands/refresh-*.md`) drive it:

```
research (WebSearch/WebFetch against allowlisted sources)
  -> draft JSON (author-supplied fields only)
  -> scripts/author_threat.py | author_event.py | author_historical.py   # the gate decides
       = pipeline/curate.finalize: normalize -> apply_gate -> sort_keys -> provenance -> validate
       = writes to the published or quarantine dir by gate result
  -> scripts/validate_data.py && scripts/build_frontend.py && pytest
  -> pipeline/changelog.regenerate()
  -> events: commit + push (a cloud session's push lands on its claude/* branch; the
     publish-events workflow re-validates scope + schema, then merges to main)
     | threats & historical: open a PR
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
  frontend.py   aggregate published records -> frontend/data/{threats,events,historical}.json
  changelog.py  regenerate CHANGELOG.md from git history
scripts/        author_threat.py, author_event.py, author_historical.py, validate_data.py,
                build_frontend.py, serve_frontend.py
frontend/       index.html (tab shell), app.js (router + panes), map.js (World Pulse map),
                styles.css, assets/blue-marble-4096.jpg (NASA, public domain)
tests/          gate, curate (all three kinds), schema, store, models round-trip
```

## 6. Frontend

Vanilla HTML/CSS/JS, no build step, **no external requests** — every byte the page loads is served
from the repo. `app.js` fetches `frontend/data/{events,threats,historical}.json` (cache-busted,
with a localStorage last-known-good fallback) and renders three hash-routed tabs (`#pulse` /
`#threats` / `#history` — shareable URLs, back-button history, unknown hashes fall back to
`#pulse`): World Pulse (flat, recency-sorted), Existential Threats (grouped by category,
severity-sorted), and the Historical Archive (grouped by era, chronological, with date badges and
estimated-deaths ranges). Each card shows verification badges and an expandable, source-linked
claims list. Quarantined records render under an "Under review" warning banner.

The **World Pulse map** (`map.js`, pulse tab only) is fully self-contained: a committed NASA Blue
Marble equirectangular basemap with drag-pan and wheel/pinch zoom, markers sized and colored by
`sort_keys.impact_rank`, hover tooltips, and click-to-scroll to the event card. Markers re-render
from every `events.json` paint, so the daily refresh updates the map automatically; `app.js` only
touches the two-method `GOMap` API, keeping a richer map library a drop-in swap.

Freshness honesty: cached figures are labeled "as of <claims' retrieved_date>" with a "live at
source" link (`event.live_source_url`); a **staleness banner** appears when `last_updated` exceeds
2 days (events) or 10 days (threats) — the Historical Archive is exempt (its `staleAfterDays` is
null, and the banner guard requires a finite threshold).

## 7. Operations

- **`validate.yml`** — on every PR/push: ruff, pytest, `validate_data.py` (the hard schema gate),
  frontend build.
- **`pages.yml`** — on push to `main` touching `frontend/**`: rebuilds the aggregates and deploys
  `frontend/` to GitHub Pages.
- **`publish-events.yml`** — the auto-publish bridge: when a cloud session pushes a `claude/*`
  branch, it merges to `main` only if the branch touches nothing but events data + the aggregate +
  CHANGELOG and passes schema validation with a byte-exact aggregate. Threats and historical
  branches are skipped (they go through PR review). This enforces the refresh commands'
  write-scope rule mechanically.
- **`staleness.yml`** — daily scheduled check that fails loudly (GitHub notification) if the
  committed `frontend/data/*.json` goes stale (>2 days events / >10 days threats;
  `historical.json` deliberately exempt) — the server-side complement to the frontend banner,
  catching a silently-dead refresh schedule.
- **Refresh schedule** — two Claude Code scheduled cloud agents: daily → `/refresh-events`, weekly →
  `/refresh-threats`. `/refresh-history` runs ad hoc, unscheduled.

## 8. History

The project began as a four-stage pipeline of independent Claude **API** calls (Generate → Verify →
Clean-up → Optimize) orchestrated by a daily GitHub Actions cron. That path spent API credits a Max
subscription can't cover, so curation moved to Claude Code and the pipeline was retired; the
deterministic trust gate it pioneered is the part that survived (now `pipeline/gate.py`). The full
blueprint and implementation live in git history — check out the tree just before commit "Delete the
legacy 4-layer API pipeline".
