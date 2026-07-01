# end-times-tracker — "World Watch"

A **fact-based** watch on the world: a live **pulse of confirmed major events** (disasters,
outbreaks, crises) alongside an ongoing tracker of **existential threats** to humanity — where every
published figure is grounded in an official, authoritative source.

It is explicitly **an aggregation of authoritative figures, not a forecast.**

> **Status:** World Pulse (events) shipped alongside the original threats tracker. Both refresh
> commands (`/refresh-events`, `/refresh-threats`) are built, tested, and manually verified
> end-to-end. **The one remaining step is configuring the two external scheduled triggers** (daily →
> `/refresh-events`, weekly → `/refresh-threats`) in the Claude Code on the web dashboard — see the
> top of [`docs/BACKLOG.md`](docs/BACKLOG.md) for the exact prompts to point them at. Until that's
> done, the dataset only refreshes when someone runs a command manually; the frontend's staleness
> banner (see Trust model below) is the signal that this hasn't happened yet.

## How it works

The dataset is curated by **Claude Code running on a Claude Max subscription** (no per-token API
spend). Both content types share the same deterministic Python trust gate — it decides what
publishes, never the model's say-so — but differ in cadence and publish model, because a discrete
"what just happened" event and a standing "what could end us" risk are genuinely different things:

- **World Pulse (events)** — `data/events/*.json`, validated against `data/schema/event.schema.json`.
  Cadence: **daily**. Curated via `/refresh-events` (`.claude/commands/refresh-events.md`) or
  `scripts/author_event.py`. **Auto-published** straight through the gate with no PR — a daily
  unattended refresh has no one to review one, so the gate alone decides verified vs. quarantined.
- **Existential Threats** — `data/threats/*.json`, validated against `data/schema/threat.schema.json`.
  Cadence: **weekly** (standing risks don't move day to day). Curated via `/refresh-threats` or
  `scripts/author_threat.py`. Updates land via a **human-reviewed PR** — see the `/refresh-threats`
  command.

The site redeploys automatically whenever `frontend/data/*.json` changes on `main`.

A four-stage pipeline of **independent** Claude *API* calls (Generate → Verify → Clean-up → Optimize)
also exists as an **optional, manual path** (`python -m pipeline.run`) for threats only; it spends API
credits and is no longer run on a schedule. Either way the same gate enforces the trust model. The
four stages:

1. **Generate** (Opus) proposes candidate threats and claims — everything it emits is `unverified`.
2. **Verify** (Opus) grounds each claim against authoritative sources via web search, then a
   deterministic **quarantine gate** (pure Python) checks every citation against a domain allowlist.
   A record publishes only with ≥1 verified claim and no disputed claims; otherwise it is quarantined.
3. **Clean-up** (Haiku) normalizes mechanically — no factual changes.
4. **Optimize** (Sonnet) tightens presentation and computes ranking. A guard asserts it never alters claims.

**Git is the database, the changelog, and the audit trail** — one JSON file per record (threat or
event), so diffs are the record of what changed. The frontend is static vanilla HTML/CSS/JS with no
build step, rendering two co-equal panes (World Pulse, then Existential Threats) from two aggregate
files, `frontend/data/events.json` and `frontend/data/threats.json`.

The full design is in [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## Trust model

- Every published claim links its source. A claim is `verified` only when its citation resolves to an
  allowlisted authoritative domain — USGS, WHO, IPCC, NASA/CNEOS, IAEA, CDC, NOAA, UN, NIST, GDACS,
  ReliefWeb, UNHCR, IMF, … (see `SOURCE_ALLOWLIST` in `pipeline/config.py`) — the check is a
  deterministic Python domain match, never the model's say-so.
- Records that fail verification are **not hidden**: they appear in an "Under review" section, clearly
  flagged as unverified, and are never presented as confirmed.
- Known limit (MVP): verification confirms that an authoritative source was *cited*, not deep semantic
  entailment that the source supports the claim. The `disputed`/`partial` statuses give reviewers a hook.
- **Staleness banner:** each pane's freshness line warns if the data hasn't refreshed recently
  (events: >2 days; threats: >10 days) — the mechanism-agnostic signal that the scheduled trigger
  (once configured) has stopped firing.

## Run it locally

```sh
pip install -e ".[dev]"

python -m pipeline.run --dry-run        # full pipeline, deterministic fixtures, $0
pytest                                  # unit tests
python scripts/validate_data.py         # schema validation (the CI hard gate)
python scripts/build_frontend.py        # build frontend/data/{threats,events}.json
python scripts/serve_frontend.py        # preview at http://localhost:8000

# One real threat against the live API (needs ANTHROPIC_API_KEY) — the cheap smoke test:
python -m pipeline.run --only-slug yellowstone-supervolcano
```

Curate without spending API credits — drive Claude Code on your Max plan:

```sh
# In a Claude Code session: research + verify current major world events, auto-published ($0 API)
/refresh-events

# ... or standing threats, which open a PR for human review instead ($0 API)
/refresh-threats nuclear winter, antibiotic resistance

# Or finalize a hand-drafted record through the same deterministic gate:
python scripts/author_event.py draft.json     # -> data/events/ or data/quarantine-events/
python scripts/author_threat.py draft.json    # -> data/threats/ or data/quarantine/
```

The API pipeline (`.github/workflows/pipeline.yml`) is **manual-only** (`workflow_dispatch`) and
needs `ANTHROPIC_API_KEY` in the repo's Actions secrets; it spends credits, so the daily cron was
removed. Re-add a `schedule:` trigger there only if you fund the API.

## How to read a threat file

Each `data/threats/<slug>.json` validates against `data/schema/threat.schema.json`:

- `assessment` — categorical `probability.estimate` (+ optional published `numeric_annual`), `severity`,
  `timeframe`, one-line `summary`.
- `claims[]` — each a checkable assertion with `source_name`, `source_url`, `retrieved_date`, and a
  per-claim `verification_status`.
- `verification` — overall `status` (verified / partial / quarantined / unverified) + `confidence`.
- `provenance` — append-only record of which layer last touched it, capped so files stay small.
- `sort_keys` — numeric ordering computed by Optimize (`severity_rank`/`probability_rank`, severity-dominant).

## How to read an event file

Each `data/events/<slug>.json` validates against `data/schema/event.schema.json`. It shares
`claims[]`, `verification`, `provenance`, `last_updated`, and `schema_version` byte-for-byte with the
threat schema — the trust spine is identical — but replaces `assessment` with an `event` block, since
a dated occurrence needs a different shape than a standing risk:

- `event.occurrence_date` / `location` / `status` (ongoing / contained / resolved) / `scale` (free
  text, e.g. `"M6.3"`, `"PHEIC"`) / `impact` (`deaths`, `displaced`, `summary`) / `live_source_url` —
  the authoritative page that keeps updating; the frontend links it as "live at source".
- `sort_keys` — `recency_rank`/`impact_rank`, **recency-dominant** (today's event outranks last
  month's), the inverse of how threats sort.

See [`CONTRIBUTING.md`](CONTRIBUTING.md) to add an event or threat by hand, or propose a new
authoritative source.
