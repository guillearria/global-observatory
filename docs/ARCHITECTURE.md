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
| Sources | `data/source-allowlist.json` — one shared allowlist, one gate | ← same | ← same |
| Domain block | `assessment` (probability × severity) | `event` (date, location, status, scale, impact) | `historical` (BCE-capable chronology, era, estimate-range impact) |
| Sort | severity-dominant | recency-first, severity-blended at render time (each impact tier buys staying power) | chronological (oldest first, grouped by era) |
| Cadence | weekly, via `/refresh-threats` | daily, via `/refresh-events` | ad hoc, via `/refresh-history` |
| Publish | **auto-publish** via the `publish` workflow — no PR for any dataset; the gate is the reviewer | ← same | ← same |
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
  `source_url` against `data/source-allowlist.json` — a deterministic Python domain
  match. A claim marked verified but citing a non-allowlisted domain is downgraded to unverified.
- The allowlist has informal tiers: official/intergovernmental agencies (USGS, WHO, UN, …),
  event-feed services (GDACS, ReliefWeb), and a scholarly/reference tier for the Historical Archive
  (Britannica, Smithsonian, national archives/museums, Our World in Data, university presses —
  deliberately no Wikipedia). One list, one gate: every kind passes the same check.
- **The allowlist is data, and refresh runs may extend it** (`data/source-allowlist.json`, validated
  by `data/schema/source-allowlist.schema.json`). This is the trust model's weakest joint and worth
  stating outright: an agent that can allowlist a domain can then cite it, so the guarantee is no
  longer "a human vetted every source" but "every source is a named institution with a written,
  published reason for being trusted". What holds it together is that additions cannot be silent —
  the schema demands a real justification, `validate_data.py` gates the file and rejects duplicates,
  the `publish` scope guard still refuses any change to `data/schema/`, and `pipeline/changelog.py`
  lists every newly allowlisted domain in `CHANGELOG.md`.
- A record publishes only with **≥1 verified claim and 0 disputed claims**; otherwise it is written
  to the kind's quarantine dir (`data/quarantine/`, `data/quarantine-events/`,
  `data/quarantine-historical/`) and rendered by the frontend under "Under review", clearly
  flagged — held back, never presented as confirmed.
- Categorical fields (a threat's severity/probability estimate, an event's status/scale) are
  editorial judgment; the **numeric claims** are what must cite an allowlisted source.
- **Known limit:** the gate verifies that an authoritative source was *cited*, not deep semantic
  entailment that the source supports the claim. The `disputed`/`partial` statuses give a later
  audit pass a hook; the README states the limit plainly.
- To add an authoritative domain, append an entry to `data/source-allowlist.json` with a written
  `justification`. It is data, so it auto-publishes like a record — the schema, the hard gate, and
  a CHANGELOG line per addition are what stand in for review (see CONTRIBUTING.md).

## 3. Data model — git is the database

One JSON file per record, serialized deterministically (`json.dumps(..., indent=2, sort_keys=True,
ensure_ascii=False)`) so git diffs are meaningful: a re-verify that confirms the same facts diffs
only `retrieved_date` + `provenance`; a changed fact produces a clear, reviewable diff — and on
events it also appends one dated `updates[]` entry. Stable `claims[].id` values keep
re-verification diffs in place. Prose fields (`description`, the kind summary) are current-state
text rewritten in place, enforced by Python prose checks (length caps + forbidden
process-language phrases, `pipeline/config.py`) that run inside `curate.finalize` and
`validate_data.py`; claim text is exempt. `CHANGELOG.md` is **generated** by
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
- Event `updates[]` — optional dated development log (`{date, text}`, newest first, capped at 30
  entries × 400 chars, Python-enforced), mirroring provenance's capped-append precedent. One
  entry per material development or correction; a no-change re-verify only bumps the confirming
  claim's `retrieved_date`. Feeds no derived field, so it is deliberately unaudited.
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
  -> commit + push, no PR (a cloud session's push lands on its claude/* branch; the
     publish workflow re-validates scope + schema + aggregate integrity, then merges to main)
```

Hand-authoring follows the same path (see CONTRIBUTING.md). There is no other write path — nothing
publishes without passing `finalize`.

## 5. Module map

```
pipeline/
  config.py     paths, rank tables, allowlisted() + the allowlist loaded from
                data/source-allowlist.json (curated data, not code — refresh runs extend it)
  gate.py       apply_gate — the deterministic quarantine gate (imports only config)
  curate.py     finalize/write + _normalize + compute_sort_keys — the whole authoring path
  models.py     deterministic dumps, slugs, run ids, provenance stamp, index_of
  schema.py     jsonschema validation + Python-side range/slug checks
  store.py      atomic per-record JSON store, kind-aware dirs
  frontend.py   aggregate published records -> frontend/data/{threats,events,historical}.json
  changelog.py  regenerate CHANGELOG.md from git history
scripts/        author_threat.py, author_event.py, author_historical.py, validate_data.py,
                build_frontend.py, serve_frontend.py
frontend/       index.html (tab shell), app.js (router: tabs + detail views, panes), map.js (World Pulse map),
                styles.css, assets/blue-marble-4096.jpg (NASA, public domain)
tests/          gate, curate (all three kinds), schema, store, models round-trip
```

## 6. Frontend

Vanilla HTML/CSS/JS, no build step, **no external requests** — every byte the page loads is served
from the repo. `app.js` fetches `frontend/data/{events,threats,historical}.json` (cache-busted,
with a localStorage last-known-good fallback) and hash-routes three list tabs plus a per-record
detail view (`#pulse` / `#threats` / `#history` and `#pulse/<id>` / `#threats/<id>` /
`#history/<id>` — shareable URLs, back-button history, unknown hashes fall back to `#pulse`, an
unknown id to a not-found note): World Pulse (flat; recency-first with severity-weighted staying
power, blended at render time from `occurrence_date`, `impact_rank`, and `status` — stored
`sort_keys` are untouched), Existential Threats (grouped by category, severity-sorted, filterable
by category and severity), and the Historical Archive (grouped by era, chronological with a
newest-first toggle, filterable by type). Every card, on all three tabs, is the same three
elements (design pass, 2026-08-26 — `docs/DESIGN-PASS.md`): a **dateline** of short structured
fields (category · country · date · status for events; severity · probability for threats; type ·
date · country for the archive), pipe-separated, with the live signal on the right — an event's
status with its dot, plus a filled pill *only* when the record is the exception (partial /
disputed / unverified / under review; `verified` is the norm and carries no label); the
**title**; and a **teaser**,
the first sentence of `description`, derived client-side (`firstSentence`, with an abbreviation
guard) and shown complete — never clamped, no ellipsis anywhere on the site. A `country` written
as prose is reduced to its bare place and dropped past 40 characters. The whole card is the link:
the title anchor's `::after` stretches over the `<article>`, which keeps `id="card-<id>"` as the
map's jump target and the title as the accessible name. The detail view renders a facts block
(full location, scale, the live-source link, last-updated, and the gate's verdict in reader
words — "7 of 7 sources confirmed · confidence high", or "3 of 4 sources confirmed · confidence
medium · 1 cited page could not be re-opened (see citations)" — with the raw `verification.notes`
string in a `title` attribute), the narrative under Overview, the numeric
lines plus the figures summary under Key figures (Assessment, for threats), the dated `updates[]`
timeline (events), and the complete source-linked citations list, always expanded — a claim shows
a status pill only when it is not verified. Quarantined records render under an "Under review"
warning banner on the list and resolve on detail routes with the same banner.

Identity chrome (same pass): a masthead with an inline SVG mark (a globe with a pulse line) beside
a Newsreader wordmark (no nav — the footer and About carry the links), the same mark as a data-URI
favicon, an `og:image` rendered from the same mark and face, a one-line footer (*Project code on
GitHub · Built by …*), and a static **About** tab (`#about`, no data, no detail routes) that
explains the site, its sourcing rule and its curator in reader language — the allowlist/gate
vocabulary stays in this document and the README, not on the page. Every list tab has a toolbar:
World Pulse filters by category and searches; Existential Threats filters by category and
severity and searches; the Archive sorts, filters by type and searches. Search is every-word-must-
match over name, description, place, category label and date text, in memory, no refetch.
The display face is **self-hosted and subsetted**
(`frontend/assets/fonts/`, SIL OFL 1.1) precisely because of the no-external-requests property — a
hosted-font `<link>` would break it; body text stays `system-ui`.

The **World Pulse map** (`map.js`, pulse tab only) is fully self-contained: a committed NASA Blue
Marble equirectangular basemap with drag-pan and wheel/pinch zoom, markers sized and colored by
`sort_keys.impact_rank`, hover tooltips, and click-to-scroll to the event card. Markers re-render
from every `events.json` paint, so the daily refresh updates the map automatically; `app.js` only
touches the two-method `GOMap` API — `setEvents(records, { describe })`, whose optional hook
supplies the tooltip's second line (the card dateline), and `invalidate()` — keeping a richer map
library a drop-in swap.

Freshness honesty: cached figures are labeled "as of <claims' retrieved_date>" on the detail view,
with a "live at source" link (`event.live_source_url`) — its one home on the site; a **staleness banner**
appears on the list panes when `last_updated` exceeds 2 days (events) or 10 days (threats) — the
Historical Archive is exempt (its `staleAfterDays` is null, and the banner guard requires a
finite threshold).

## 7. Operations

- **`validate.yml`** — on every push to `main` (and on a PR, if anyone opens one): ruff, pytest,
  `validate_data.py` (the hard schema gate), frontend build. Also `workflow_dispatch`-able, and
  dispatched by `publish` after each auto-merge:
  `publish` pushes to `main` with `GITHUB_TOKEN`, and token pushes do not retrigger `push`
  workflows, so without that dispatch `validate` would silently stop running on `main`.
  Ruff is pinned to a minor range in `pyproject.toml` with an explicit `[tool.ruff.lint] select` —
  a floating version once turned CI red on a data-only change when ruff widened its defaults.
- **`pages.yml`** — on push to `main` touching `frontend/**`: rebuilds the aggregates and deploys
  `frontend/` to GitHub Pages.
- **`publish.yml`** — the auto-publish bridge for all three datasets: when a cloud session pushes a
  `claude/*` branch, it merges to `main` only if the branch touches nothing but curated data
  (`data/{events,threats,historical,quarantine*}/`, `data/source-allowlist.json`) + the aggregates
  + CHANGELOG, and passes schema validation with byte-exact aggregates. `data/schema/` is excluded —
  it defines the gate, so it is code, and that asymmetry is the point: a refresh run can add a
  domain to the allowlist but never loosen the rules that check it. Anything else is left for a
  human merge. This enforces the refresh commands' write-scope rule mechanically, and is the reason
  no dataset needs a review queue.
- **`staleness.yml`** — daily scheduled check that fails if the committed `frontend/data/*.json`
  goes stale (>2 days events / >10 days threats; `historical.json` deliberately exempt) — the
  server-side complement to the frontend banner, catching a silently-dead refresh schedule.
- **`notify.yml`** — the only alarm that leaves GitHub. A single `workflow_run` listener on
  `staleness`, `publish`, `validate` and `pages` that pushes any failure to Telegram via
  `scripts/notify.py`. It exists because a red CI run is not a signal unless somebody is
  subscribed to it: `staleness` ran red for 11 straight days in July 2026 while two verified
  threat records were being lost, because auto-publish made the "last committer" GitHub notifies a
  bot. One listener rather than a step per workflow, so new failure modes in existing workflows
  are covered by default; the cost is that a *new* workflow must be added to its `workflows:` list.
  Needs the `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` repository secrets — without them it exits
  0 with a notice rather than turning every failure into a second red run, so **an unarmed
  notifier is silent by design**. Because that silence is indistinguishable from having nothing to
  report, `workflow_dispatch` is a self-test (`gh workflow run notify.yml`) that sends a message
  and *fails* when the secrets are unset. `scripts/notify.py` never retries: a timed-out send is
  ambiguous, and retrying an ambiguous send double-posts.
- **Refresh schedule** — two Claude Code scheduled cloud agents: daily → `/refresh-events`, weekly →
  `/refresh-threats`. `/refresh-history` runs ad hoc, unscheduled.

## 8. History

The project began as a four-stage pipeline of independent Claude **API** calls (Generate → Verify →
Clean-up → Optimize) orchestrated by a daily GitHub Actions cron. That path spent API credits a Max
subscription can't cover, so curation moved to Claude Code and the pipeline was retired; the
deterministic trust gate it pioneered is the part that survived (now `pipeline/gate.py`). The full
blueprint and implementation live in git history — check out the tree just before commit "Delete the
legacy 4-layer API pipeline".
