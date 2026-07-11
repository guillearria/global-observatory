# Global Observatory

A **fact-based** observatory of the world, in three tabs:

- **World Pulse** — a live pulse of confirmed major events (disasters, outbreaks, crises), plotted
  on a world map with markers that scale with impact.
- **Existential Threats** — an ongoing tracker of standing risks to humanity, by category.
- **Historical Archive** — major events from the dawn of civilization to the recent past, on one
  chronological timeline.

Every published figure is grounded in an official, authoritative source. It is explicitly **an
aggregation of authoritative figures, not a forecast.**

**Who runs this:** built and maintained by [Guillermo Arria-Devoe](https://github.com/guillearria)
as a public-good demonstration that an AI curator can publish autonomously without ever getting
the final say on truth — a deterministic gate does. Questions and contributions welcome.

> **Status:** the refresh commands are **scheduled as Claude Code cloud routines**: daily →
> `/refresh-events` (09:00 UTC, auto-publishes through the gate), weekly → `/refresh-threats`
> (Mondays 10:00 UTC, opens a PR). `/refresh-history` runs ad hoc. Routines are managed at
> claude.ai/code/routines. The frontend's staleness banner and the scheduled `staleness` workflow
> (see Trust model below) are the signals if a routine silently stops firing.

## How it works

The dataset is curated by **Claude Code running on a Claude Max subscription** (no per-token API
spend). All three content types share the same deterministic Python trust gate — it decides what
publishes, never the model's say-so — but differ in cadence and publish model, because a discrete
"what just happened" event, a standing "what could end us" risk, and a "what once happened"
archive entry are genuinely different things:

- **World Pulse (events)** — `data/events/*.json`, validated against `data/schema/event.schema.json`.
  Cadence: **daily**. Curated via `/refresh-events` (`.claude/commands/refresh-events.md`) or
  `scripts/author_event.py`. **Auto-published** through the gate with no PR — a daily unattended
  refresh has no one to review one, so the gate alone decides verified vs. quarantined. (Cloud
  sessions can only push to their own branch, so the `publish-events` workflow re-validates the
  branch, checks it touches only events data, and merges it into `main`.)
- **Existential Threats** — `data/threats/*.json`, validated against `data/schema/threat.schema.json`.
  Cadence: **weekly** (standing risks don't move day to day). Curated via `/refresh-threats` or
  `scripts/author_threat.py`. Updates land via a **human-reviewed PR** — see the `/refresh-threats`
  command.
- **Historical Archive** — `data/historical/*.json`, validated against
  `data/schema/historical.schema.json`. Cadence: **ad hoc** (an archive grows when there is
  something worth adding, and cannot go stale). Curated via `/refresh-history` or
  `scripts/author_historical.py`. Updates land via a **human-reviewed PR**, like threats.

The site redeploys automatically whenever `frontend/data/*.json` changes on `main`.

**Git is the database, the changelog, and the audit trail** — one JSON file per record, so diffs
are the record of what changed. The frontend is static vanilla HTML/CSS/JS with no build step and
**no external requests** (even the map's NASA Blue Marble basemap is committed to the repo). It
renders three hash-routed tabs — `#pulse`, `#threats`, `#history` — from three aggregate files,
`frontend/data/events.json`, `frontend/data/threats.json`, and `frontend/data/historical.json`.

The full design is in [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## Trust model

- Every published claim links its source. A claim is `verified` only when its citation resolves to an
  allowlisted authoritative domain — USGS, WHO, IPCC, NASA/CNEOS, IAEA, CDC, NOAA, UN, NIST, GDACS,
  ReliefWeb, UNHCR, IMF, … plus a scholarly/reference tier for historical sourcing (Britannica,
  Smithsonian, Library of Congress, national archives and museums, Our World in Data, university
  presses; deliberately no Wikipedia) — see `SOURCE_ALLOWLIST` in `pipeline/config.py`. The check is
  a deterministic Python domain match, never the model's say-so.
- Records that fail verification are **not hidden**: they appear in an "Under review" section, clearly
  flagged as unverified, and are never presented as confirmed.
- Known limit (MVP): verification confirms that an authoritative source was *cited*, not deep semantic
  entailment that the source supports the claim. The `disputed`/`partial` statuses give reviewers a hook.
- **Staleness banner:** the events and threats tabs warn if the data hasn't refreshed recently
  (events: >2 days; threats: >10 days) — the mechanism-agnostic signal that the refresh schedule
  has stopped firing. A scheduled GitHub Actions workflow
  (`.github/workflows/staleness.yml`) runs the same check server-side daily and fails loudly, so
  a dead schedule triggers a notification instead of waiting for someone to load the page. The
  Historical Archive is exempt — an archive cannot go stale.

## The map

The World Pulse tab plots every event with coordinates (`event.location.lat`/`lon`, optional
fields) on a self-contained equirectangular NASA Blue Marble basemap: drag to pan, scroll or pinch
to zoom, markers sized and colored by `sort_keys.impact_rank` (grey → blue → amber → red), click a
marker to jump to its card. Markers are drawn from the same `events.json` the cards render from, so
every daily refresh updates the map automatically. No tile server, no map library, no external
requests.

## Run it locally

```sh
pip install -e ".[dev]"

pytest                                  # unit tests
python scripts/validate_data.py         # schema validation (the CI hard gate)
python scripts/build_frontend.py        # build frontend/data/{threats,events,historical}.json
python scripts/serve_frontend.py        # preview at http://localhost:8000
```

Curate without spending API credits — drive Claude Code on your Max plan:

```sh
# In a Claude Code session: research + verify current major world events, auto-published ($0 API)
/refresh-events

# ... or standing threats, which open a PR for human review instead ($0 API)
/refresh-threats nuclear winter, antibiotic resistance

# ... or landmark historical events, also via PR ($0 API)
/refresh-history the Bronze Age collapse, the Antonine Plague

# Or finalize a hand-drafted record through the same deterministic gate:
python scripts/author_event.py draft.json       # -> data/events/ or data/quarantine-events/
python scripts/author_threat.py draft.json      # -> data/threats/ or data/quarantine/
python scripts/author_historical.py draft.json  # -> data/historical/ or data/quarantine-historical/
```

## How to read a threat file

Each `data/threats/<slug>.json` validates against `data/schema/threat.schema.json`:

- `assessment` — categorical `probability.estimate` (+ optional published `numeric_annual`), `severity`,
  `timeframe`, one-line `summary`.
- `claims[]` — each a checkable assertion with `source_name`, `source_url`, `retrieved_date`, and a
  per-claim `verification_status`.
- `verification` — overall `status` (verified / partial / quarantined / unverified) + `confidence`.
- `provenance` — append-only record of which layer last touched it, capped so files stay small.
- `sort_keys` — numeric ordering computed by `curate.compute_sort_keys` (`severity_rank`/`probability_rank`, severity-dominant).

## How to read an event file

Each `data/events/<slug>.json` validates against `data/schema/event.schema.json`. It shares
`claims[]`, `verification`, `provenance`, `last_updated`, and `schema_version` byte-for-byte with the
threat schema — the trust spine is identical — but replaces `assessment` with an `event` block, since
a dated occurrence needs a different shape than a standing risk:

- `event.occurrence_date` / `location` (`country`, `region`, optional `lat`/`lon` for the map) /
  `status` (ongoing / contained / resolved) / `scale` (free text, e.g. `"M6.3"`, `"PHEIC"`) /
  `impact` (`deaths`, `displaced`, `summary`) / `live_source_url` — the authoritative page that
  keeps updating; the frontend links it as "live at source".
- `sort_keys` — `recency_rank`/`impact_rank`, **recency-dominant** (today's event outranks last
  month's), the inverse of how threats sort.

## How to read a historical file

Each `data/historical/<slug>.json` validates against `data/schema/historical.schema.json`. Same
trust spine again; the `historical` block replaces `event`, because the deep past needs a different
shape than the news:

- `historical.year_start` / `year_end` — **signed astronomical years** (0 = 1 BCE, −2999 = 3000 BCE),
  since ISO dates can't represent BCE; `date_display` is the human text the frontend shows
  (e.g. `"c. 1177 BCE"`, `"1347–1351"`).
- `era` — ancient / classical / medieval / early-modern / modern / contemporary; the timeline groups
  by it.
- `impact.deaths_low` / `deaths_high` — an **estimate range** quoted as the source states it
  (the Black Death is "75–200 million", not a number someone invented), with a prose `summary`.
- `sort_keys` — `chronology_rank`/`impact_rank`, **chronology-dominant** (the timeline reads oldest
  → newest).

See [`CONTRIBUTING.md`](CONTRIBUTING.md) to add a record by hand, or propose a new
authoritative source.
