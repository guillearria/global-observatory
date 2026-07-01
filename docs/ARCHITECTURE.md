# end-times-tracker — Architecture Blueprint

> **Status: implemented, with one operating-model change since this was written.**
> The system below is built. The original design called for a *fully-automated daily API cron*.
> In practice that path spends Anthropic **API credits** (a Max/Pro subscription cannot pay for raw
> API calls), so recurring curation now runs through **Claude Code on a Max subscription** instead:
> it researches and drafts cited claims with web search, and `scripts/author_threat.py` /
> `pipeline.curate` run each record through the **same deterministic quarantine gate** described
> here before a human-reviewed PR. The four-layer API pipeline remains as an optional manual path
> (`python -m pipeline.run`). **The trust model is unchanged** — the allowlist gate still has the
> final say regardless of who proposes a claim.

> **Status update 2: a second content type, World Pulse, was added on top of this design — see §12.**
> The project now curates two kinds of record through the *same* trust spine: standing **threats**
> (this document, unchanged) and dated **events** (`data/events/*.json`, confirmed major world
> disasters/crises, refreshed daily). The generalization is a `kind: "threat"|"event"` parameter
> threaded through the shared functions (`schema.validate`, `store.write_record`,
> `optimize.compute_sort_keys`, `curate.finalize`/`write`) with `kind="threat"` as the default — the
> allowlist gate (`verify.apply_gate`) itself needed **zero changes**, since it only ever inspects
> `claims[]`. `/refresh-events` and `/refresh-threats` are both built and manually verified
> end-to-end. **The one remaining piece is external**: a Claude Code on the web scheduled trigger,
> configured by a human in the dashboard (this cannot be done from inside a coding session) — see the
> top of `docs/BACKLOG.md` for the exact configuration. Until that's set up, both refresh commands
> must be run manually; the frontend's staleness banner is the signal if a configured trigger later
> stops firing.

## 1. What this project is

A living, continuously-updating, **fact-based** watch on the world, with two parts:

- **Existential Threats** (this document's original subject) — standing risks to humanity, e.g.
  Yellowstone supervolcano, nuclear war, food/water shortages, biological weapons, runaway AI,
  asteroid impact, pandemics, climate tipping points. Assessment-based (probability × severity);
  genuinely doesn't move day to day, so it refreshes weekly.
- **World Pulse** (§12) — a daily pulse of *confirmed, currently major* world events: disasters,
  outbreaks, humanitarian crises. Dated, discrete occurrences rather than standing risks, so they get
  their own schema and refresh daily. Everything below through §11 describes the threats side; the
  design generalizes to events with minimal duplication (§12).

Core principles:

- **Highly fact-based.** Every published claim is grounded in an official / authoritative
  source (USGS, WHO, IPCC, NASA/CNEOS, IAEA, CDC, NOAA, UN…) with a citation.
- **Unverifiable claims are held back, never shown.** Material that fails verification is
  quarantined, not published.
- **Low-friction curation, human-reviewed.** The dataset is refreshed by Claude Code (Max plan,
  web search) or the optional API pipeline; either way the deterministic gate decides what
  publishes, and changes land via PR. *(Originally specified as a fully-automated daily cron — see
  the status note above for why that path is now optional/manual.)*
- **Independent model layers.** Four stages — Generate, Verify, Clean-up, Optimize —
  each run as separate model calls that **do not share context**.
- **Git is the database, the changelog, and the audit trail.** One JSON file per threat;
  diffs are the record of what changed and why.
- **Open source from day one**, dependency-light, no production hosting beyond static pages.

It is explicitly **an aggregation of authoritative figures, not a forecast.**

## 2. Locked design decisions

| Decision | Choice | Rationale |
|---|---|---|
| Scope (this round) | **Blueprint document only** | Review/cross-verify before building |
| Pipeline language | Python + official `anthropic` SDK | First-class SDK, easy file/data handling |
| Frontend | Vanilla HTML/CSS/JS, no build step | Dependency-light, static-host friendly |
| Data store | One JSON file per threat in the repo | Git diffs = audit trail; zero DB infra |
| Layer model | 4 independent `messages.create` calls | No shared context between stages |
| Orchestration | GitHub Actions cron, auto-commit | No human in the loop |
| Models | `claude-opus-4-8` (Generate, Verify), `claude-sonnet-4-6` (Optimize), `claude-haiku-4-5` (Clean-up) | Strongest model on judgment-heavy stages; cheaper tiers on mechanical ones |

### API facts the design depends on (current and verified)

- Model IDs `claude-opus-4-8`, `claude-sonnet-4-6`, `claude-haiku-4-5` are current.
- Thinking: `thinking={"type":"adaptive"}` only. `budget_tokens` returns **400** on opus-4-8.
- Effort: `output_config={"effort":"high"}` (`low|medium|high|max`; opus-4-8 also `xhigh`).
  Nested inside `output_config`, not top-level. **Haiku does not support `effort`** — omit it.
- Structured output: `output_config={"format":{"type":"json_schema","schema":{...}}}`.
  Schema limits: **no `minLength`/`maxLength`/`minimum`/`maximum`/`pattern`, no recursion**,
  every object needs `additionalProperties:false`. Validate ranges in Python.
- Assistant **prefill 400s** on opus-4-8 — never used; structured outputs replace it.
- Web search tool: `{"type":"web_search_20260209","name":"web_search"}` (and
  `web_fetch_20260209`). Citations return as citation blocks; success `content` is a
  *list*, error `content` is an *object* (`{error_code: ...}`) — branch on that.
- **⚠️ Critical constraint:** web-search **citations + `output_config.format` returns 400**.
  A single call cannot both browse-with-citations *and* emit schema JSON. This is the single
  most important correction to a naive design and **forces Verify into two independent
  sub-calls** (see §5).

## 3. Repository layout (intended)

```
end-times-tracker/
├── README.md  CONTRIBUTING.md  CHANGELOG.md  LICENSE(MIT)
├── .gitignore  .env.example          # ANTHROPIC_API_KEY=...
├── pyproject.toml                    # deps: anthropic, jsonschema; ruff/pytest
│
├── docs/
│   └── ARCHITECTURE.md               # this document
│
├── data/
│   ├── threats/<slug>.json           # source of truth, one file per threat
│   ├── quarantine/<slug>.json        # failed verification, NOT published
│   └── schema/threat.schema.json     # JSON Schema (draft 2020-12)
│
├── pipeline/
│   ├── run.py                        # orchestrator (the single `run`)
│   ├── config.py                     # model ids, effort tiers, paths, source allowlist
│   ├── client.py                     # build_client(), context-free call_layer(), DryRunClient
│   ├── models.py                     # dataclasses + deterministic JSON dump
│   ├── store.py                      # atomic read/write, slug<->path
│   ├── schema.py                     # load + validate records
│   ├── changelog.py                  # regenerate CHANGELOG.md from git history
│   ├── layers/{generate,verify,cleanup,optimize}.py
│   └── prompts/{generate,verify,cleanup,optimize}.system.md
│
├── frontend/
│   ├── index.html  styles.css  app.js
│   └── data/threats.json             # BUILT aggregate the page fetches
│
├── scripts/{build_frontend,validate_data,serve_frontend}.py
├── tests/{test_schema,test_store,test_models_roundtrip}.py + fixtures/
└── .github/workflows/{pipeline,validate}.yml
```

**JSON over YAML for records:** `json.dumps(..., indent=2, sort_keys=True, ensure_ascii=False)`
is deterministic and line-oriented, so diffs are meaningful; the browser loads it natively with
`fetch().then(r => r.json())` — no YAML parser shipped to the client.

## 4. Threat data schema

`data/schema/threat.schema.json` (draft 2020-12). Top-level object, `additionalProperties:false`.
Kept flat (range checks live in Python, since structured outputs strip numeric/string constraints).

| Field | Type | Notes |
|---|---|---|
| `schema_version` | string | e.g. `"1.0"`; lets the pipeline migrate records |
| `id` | string | stable slug, equals filename sans `.json`, `^[a-z0-9-]+$` |
| `name` | string | display name |
| `category` | enum | `cosmic`\|`geological`\|`nuclear`\|`biological`\|`climate`\|`technological`\|`resource`\|`societal` |
| `description` | string | plain-language, general-public audience |
| `assessment` | object | quantified core (below) |
| `claims` | array<Claim> | cited factual claims (below) |
| `verification` | object | status + confidence (below) |
| `provenance` | object | which layer last touched it + when (below) |
| `last_updated` | string | ISO-8601 UTC |
| `sort_keys` | object | numeric ordering fields written by Optimize |

- **`assessment`**: `probability {window, estimate(very-low..very-high), numeric_annual|null}`
  (categorical estimate always present; optional numeric annual probability when an
  authoritative figure exists), `severity (regional|continental|civilizational|extinction)`,
  `timeframe` (short string), `summary` (one sentence).
- **`claims[]`**: `{id (stable: claim-1…), text, source_name, source_url, retrieved_date,
  verification_status(verified|unverified|disputed)}`. Stable IDs mean re-verification diffs in
  place rather than reshuffling.
- **`verification`**: `{status(verified|partial|quarantined|unverified), confidence(low|medium|high), notes}`.
- **`provenance`**: `{last_layer, last_run_id, history[] of {layer, run_id, at}}`, append-only,
  capped (~20) so files don't grow unbounded.
- **`sort_keys`**: `{severity_rank int 1–4, probability_rank int 1–5, composite number}`.

**Diff-friendliness is engineered, not incidental:** stable `claims[].id` + capped `history` +
deterministic dump mean a re-verify that confirms the same facts produces a minimal diff (just
`retrieved_date` + `provenance`); a *changed* fact produces a clear, reviewable diff. This is what
makes "git history IS the changelog" actually work.

### Worked example — `data/threats/yellowstone-supervolcano.json`

```json
{
  "schema_version": "1.0",
  "id": "yellowstone-supervolcano",
  "name": "Yellowstone Supervolcano",
  "category": "geological",
  "description": "A large caldera system beneath Yellowstone National Park capable of a 'supereruption' that would blanket much of North America in ash and inject climate-altering aerosols into the stratosphere. Such eruptions are extraordinarily rare and there is no evidence one is imminent.",
  "assessment": {
    "probability": {
      "window": "next-100-years",
      "estimate": "very-low",
      "numeric_annual": 0.00000073
    },
    "severity": "continental",
    "timeframe": "No reliable short-term forecast. The three largest past eruptions occurred ~2.1M, ~1.3M, and ~0.64M years ago.",
    "summary": "A continent-scale disaster with extremely low annual probability and no current signs of imminent eruption."
  },
  "claims": [
    {
      "id": "claim-1",
      "text": "The USGS estimates the annual probability of a Yellowstone supereruption at roughly 1 in 730,000.",
      "source_name": "USGS Yellowstone Volcano Observatory",
      "source_url": "https://www.usgs.gov/observatories/yvo/frequently-asked-questions",
      "retrieved_date": "2026-06-28",
      "verification_status": "verified"
    },
    {
      "id": "claim-2",
      "text": "Yellowstone has produced three caldera-forming eruptions in the past ~2.1 million years.",
      "source_name": "USGS Yellowstone Volcano Observatory",
      "source_url": "https://www.usgs.gov/volcanoes/yellowstone",
      "retrieved_date": "2026-06-28",
      "verification_status": "verified"
    }
  ],
  "verification": {
    "status": "verified",
    "confidence": "high",
    "notes": "Both quantitative claims grounded in USGS primary sources."
  },
  "provenance": {
    "last_layer": "optimize",
    "last_run_id": "2026-06-28T06-00-12Z-a1b2c3",
    "history": [
      { "layer": "generate", "run_id": "2026-06-28T06-00-12Z-a1b2c3", "at": "2026-06-28T06:00:14Z" },
      { "layer": "verify",   "run_id": "2026-06-28T06-00-12Z-a1b2c3", "at": "2026-06-28T06:01:48Z" },
      { "layer": "cleanup",  "run_id": "2026-06-28T06-00-12Z-a1b2c3", "at": "2026-06-28T06:02:05Z" },
      { "layer": "optimize", "run_id": "2026-06-28T06-00-12Z-a1b2c3", "at": "2026-06-28T06:02:30Z" }
    ]
  },
  "last_updated": "2026-06-28T06:02:30Z",
  "sort_keys": { "severity_rank": 3, "probability_rank": 1, "composite": 41.5 }
}
```

> The numeric values above are illustrative for the schema shape. In the real system every such
> figure is set by the Verify layer from a live, cited authoritative source.

## 5. The four independent layers

**Independence is structural, not conventional.** `pipeline/client.py:call_layer()` always builds a
single-turn `messages=[{"role":"user", ...}]` with a fresh `system` prompt — there is deliberately
**no parameter to pass prior messages**. The only channel between layers is the **files on disk**
(mirrored by an in-memory record dict within one run). No `ConversationManager`, no shared message
list, no passing a `Message` object downstream.

Why this matters: shared context would let Generate's speculative framing bias Verify's grounding,
and let an earlier hallucination ride along as "established context" the next model treats as given.
Fresh context forces each layer to re-derive its judgment from the **persisted record only** — the
auditable, file-as-truth property the product needs.

Reference wrapper (cannot share context by construction):

```python
# pipeline/client.py
def call_layer(client, *, model, system, user_content, effort=None, fmt=None, tools=None):
    output_config = {}
    if effort: output_config["effort"] = effort
    if fmt:    output_config["format"] = fmt
    kwargs = dict(
        model=model, max_tokens=16000, system=system,
        thinking={"type": "adaptive"},
        messages=[{"role": "user", "content": user_content}],  # always single-turn
    )
    if output_config: kwargs["output_config"] = output_config
    if tools:         kwargs["tools"] = tools
    return client.messages.create(**kwargs)
```

### Layer 1 — Generate

- **Responsibility:** propose new threats and updated `description`/`assessment`/`claims` text.
  Does **not** verify facts or finalize ranking.
- **Input:** a compact index of existing slugs + `name`/`category`/`assessment.summary` (not full
  records — avoids anchoring on stale claims), plus the fixed threat-domain list.
- **Output:** schema-valid JSON via `output_config.format`; all `claims[].verification_status` and
  `verification.status` forced to `"unverified"`.
- **Model:** `claude-opus-4-8`, `effort:"high"` — the most judgment-heavy, coverage-setting step.
- **Prompt shape:** "Propose candidate threat records. Every claim must be a checkable assertion
  with a *named candidate source*, but you have no web access — mark everything `unverified`. Prefer
  claims an official body would publish. Do not invent numeric probabilities; leave `numeric_annual`
  null when unsure."

### Layer 2 — Verify (the trust core)

- **Responsibility:** ground each claim against authoritative sources via web search, attach real
  citations, set per-claim status, quarantine what can't be grounded.
- **Model:** `claude-opus-4-8`, `effort:"high"`.
- **Two independent sub-calls** (because citations + `output_config.format` → 400):
  1. **Search call:** `tools=[web_search_20260209, web_fetch_20260209]`, **no** `output_config.format`.
     Python extracts URLs/titles/quoted text from the returned **citation blocks** — not from model
     free-text (this is where citation hallucination is prevented).
  2. **Structure call:** a *fresh* opus call, no tools, `output_config.format` = schema, fed the
     record + the extracted citation artifacts → emits schema-valid JSON with
     `source_url/source_name/retrieved_date` filled from real citations and each
     `verification_status` set.
- **Quarantine gate (deterministic, Python):**
  - Citations must resolve to a domain on an **authoritative allowlist** in `config.py`
    (`usgs.gov`, `who.int`, `ipcc.ch`, `nasa.gov`, `cneos.jpl.nasa.gov`, `iaea.org`, `cdc.gov`,
    `noaa.gov`, `un.org`, …). A non-allowlisted domain downgrades the claim to `unverified`.
  - A record publishes only with **≥1 `verified` claim and 0 `disputed` headline claims**.
  - Failures are written to `data/quarantine/<slug>.json` and **excluded from `data/threats/`** —
    so the frontend physically cannot display unverified material.

  The gate is a Python domain check over real citation blocks, not the model's say-so — the concrete
  defense against hallucinated facts slipping through.

### Layer 3 — Clean-up

- **Responsibility:** mechanical normalization only — schema coercion, enum/casing normalization,
  source-name normalization (`"U.S. Geological Survey"` → `"USGS"`), claim & threat dedupe, stable
  claim sort by `id`, well-formed UTC timestamps. **No factual changes.**
- **Model:** `claude-haiku-4-5` (no `effort` — haiku doesn't support it). Cheap, high-volume,
  mechanical.
- **Dedupe by proposal, not silent deletion:** merges are proposed as a `_merge_into: <slug>` field
  that Python executes deterministically.

### Layer 4 — Optimize

- **Responsibility:** presentation + ranking — tighten `description`/`summary` for a general
  audience, compute `sort_keys` (severity_rank, probability_rank, composite). Must **not** touch
  `claims` text or `source_url`s.
- **Model:** `claude-sonnet-4-6`, `effort:"medium"`. Operates over the whole corpus (needs relative
  context to rank).
- **Guard:** Python asserts `claims` are byte-identical pre/post Optimize and reverts any drift.

### Enforced contracts (Python guards after each layer)

- Schema validation on every record (hard stop on invalid).
- Claims immutable in Optimize.
- Only Verify may introduce a `source_url` (Generate/Cleanup/Optimize cannot).
- Quarantine gate before write.

These turn the layer boundaries into enforceable contracts rather than conventions.

## 6. Orchestration

```python
# pipeline/run.py
def run(dry_run: bool, only_slug: str | None):
    run_id = utc_now_compact() + "-" + short_random()
    client = build_client()                          # reads ANTHROPIC_API_KEY (or DryRunClient)
    records = store.load_all()                        # data/threats/*.json -> dict[slug]=record

    proposals = generate.run(index_of(records), client=client, run_id=run_id)  # all 'unverified'
    merged    = merge_proposals(records, proposals)   # Python decides create vs update by slug

    verified, quarantined = [], []
    for rec in merged:
        v = verify.run(rec, client=client, run_id=run_id)   # search -> citations -> structure
        (quarantined if v["verification"]["status"] == "quarantined" else verified).append(v)

    cleaned = [cleanup.run(rec, index_of(merged), client=client, run_id=run_id) for rec in verified]
    cleaned = apply_merges(cleaned)                   # execute _merge_into deterministically

    optimized = optimize.run(cleaned, client=client, run_id=run_id)
    assert claims_unchanged(cleaned, optimized)       # guard

    for rec in optimized:
        schema.validate(rec)                          # hard stop on invalid
    if dry_run:
        print_summary(); return
    store.write_all(optimized)                        # data/threats/*.json (atomic, sorted-key JSON)
    store.write_quarantine(quarantined)               # data/quarantine/*.json
    build_frontend()                                  # frontend/data/threats.json
    changelog.regenerate()                            # CHANGELOG.md from git log
```

- `--only-slug` runs the full four layers for a single threat (cheap real run for testing).
- `--dry-run` exercises everything *except* API calls and writes (uses `DryRunClient` fixtures).

### GitHub Actions — `.github/workflows/pipeline.yml`

```yaml
name: pipeline
on:
  schedule: [{ cron: "0 6 * * *" }]     # daily 06:00 UTC
  workflow_dispatch: {}                  # manual trigger
permissions: { contents: write }         # commit results back
concurrency: { group: pipeline, cancel-in-progress: false }
jobs:
  run:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - run: pip install -e .
      - name: Run pipeline
        env: { ANTHROPIC_API_KEY: "${{ secrets.ANTHROPIC_API_KEY }}" }
        run: python -m pipeline.run
      - name: Validate before commit
        run: python scripts/validate_data.py          # hard gate; non-zero aborts commit
      - name: Commit results
        run: |
          git config user.name  "end-times-bot"
          git config user.email "bot@users.noreply.github.com"
          git add data/ frontend/data/ CHANGELOG.md
          git diff --cached --quiet || git commit -m "pipeline run $(date -u +%FT%TZ)"
          git push
```

- **`ANTHROPIC_API_KEY` lives in GitHub repo Actions secrets**, injected as the env var the SDK
  auto-reads. `.env` is gitignored; `.env.example` documents it.
- **No human in the loop:** cron triggers → four layers → validate → commit the diff back. The
  commit *is* the changelog entry. `concurrency` prevents overlapping runs;
  `git diff --cached --quiet || commit` means no-op runs produce no empty commits.
- A separate Pages publish step (or `pages.yml`) serves `frontend/` after each data commit.
- `validate.yml` runs schema validation + pytest + frontend build on PRs.

## 7. Frontend

Vanilla HTML/CSS/JS, zero build step, zero framework.

- `scripts/build_frontend.py` aggregates all published records into a single
  `frontend/data/threats.json` each run (the browser fetches one file, not N).
- `app.js`: `fetch('./data/threats.json?t=' + Date.now())` → group by `category` → within each group
  sort by `sort_keys.composite` desc → render cards (name, `assessment.summary`, probability +
  severity badges, `last_updated`, expandable claims list where each claim links `source_url` labeled
  `source_name` with its `retrieved_date` and `verification_status`). Top banner = max `last_updated`.
- **Trust signals in the UI:** each claim shows its `verification_status`; `verification.confidence`
  renders as a badge. Because quarantined records are never written to `data/threats/`, the frontend
  *cannot* display unverified material — the guarantee is enforced at the data layer.
- **"Continuously updating"** = the page is rebuilt and re-published from data on every pipeline run.
  No server; the static page + freshly-committed `threats.json` is the whole mechanism. The
  `?t=` cache-bust ensures viewers see the latest after a deploy.

## 8. Open source + changelog

- **README** — what it is (aggregation of authoritative figures, *not a forecast*), the trust model,
  architecture diagram, local-run instructions, how to read a threat file.
- **CONTRIBUTING** — schema contract, the layer rules (Verify owns citations; Optimize can't touch
  claims), how to hand-add a threat (`data/threats/<slug>.json` + `validate_data.py`), and the
  source-allowlist PR process.
- **CHANGELOG** — **generated**, not hand-written. `pipeline/changelog.py` runs
  `git log --name-status` over `data/threats/**` and renders dated sections per pipeline commit
  (added / updated / quarantined slugs), annotated with `provenance`. Git history is canonical;
  CHANGELOG.md is a human-readable projection of it.
- **LICENSE** — MIT.

## 9. Verification & testing plan

- **Dry-run, no tokens:** `python -m pipeline.run --dry-run`. `client.py` provides a `DryRunClient`
  returning canned schema-valid fixture responses per layer (selected when `--dry-run` or
  `ANTHROPIC_API_KEY` is unset). Exercises full orchestration, all guards, schema validation,
  dedupe/merge, and the frontend build for $0.
- **Real single-threat run:** `python -m pipeline.run --only-slug nuclear-war`. Runs all four layers
  (live API + web search) for one threat — the cheap smoke test before enabling the cron.
- **Schema validation:** `python scripts/validate_data.py` validates every `data/threats/*.json` with
  `jsonschema`; non-zero exit fails CI and blocks commit.
- **Unit tests (`pytest`):** schema round-trip byte-stability (serialize→parse→serialize), deterministic
  JSON dump, store atomic write + slug↔path, quarantine-gate logic (a disputed headline claim must
  quarantine).
- **Local frontend preview:** `python scripts/serve_frontend.py` → `localhost:8000`.

## 10. Risks & explicit cut-lines

1. **Hallucinated facts past Verify** (the central risk): mitigated by programmatic citation
   extraction from citation blocks, the deterministic domain allowlist, the publish gate, and
   quarantine-not-publish. **Known limit:** the MVP verifies *that an authoritative source was cited*,
   not deep semantic entailment that the source actually supports the claim — stated plainly in the
   README; the `disputed`/`partial` statuses give reviewers a hook.
2. **API cost:** haiku for Clean-up, sonnet for Optimize, one Verify-search call per record (bounded
   web-search `max_uses`), daily (not hourly) cron, `--dry-run`/`--only-slug` for dev, `concurrency`
   preventing runaway runs. **Cut-line:** no batch API, no prompt caching in the MVP (obvious v2 levers).
3. **Citation rot:** `retrieved_date` on every claim + re-verification each run; a dead link downgrades
   to `unverified` and may quarantine on the next run. **Cut-line:** no Wayback/archival in the MVP.
4. **Scope creep:** bounded by the locked decisions and the explicit NOT-list.

**Deliberately NOT in the MVP:** production hosting beyond static Pages; any database; auth/accounts;
semantic entailment checking of citations; multilingual content; per-region/per-country breakdowns;
Bayesian numeric risk modeling (categorical estimates + optional published numerics only); batch/caching
cost optimization; real-time/webhook triggers (cron only); and any agent-framework / Managed-Agents loop
(the four layers are plain, independent `messages.create` calls).

## 11. Open questions for cross-verification

These are the points most worth a second LLM's scrutiny:

1. **Citation trust depth.** Is "an authoritative domain was cited" a strong enough bar for v1, or
   should Verify also check entailment (e.g. a second skeptic call asked to *refute* each claim)?
2. **Allowlist coverage.** Which authoritative sources are missing for categories like
   `technological` (AI risk) and `societal`, where official quantified figures are scarce?
3. **Probability semantics.** Is the categorical-estimate-plus-optional-numeric split the right way to
   avoid spurious precision, or should some categories carry ranges/intervals instead?
4. **Generate ↔ Verify independence.** Does feeding Generate only a compact index (not full records)
   risk losing useful prior verification context — and is that loss worth the de-biasing benefit?
5. **Quarantine UX.** Should quarantined threats be *invisible* (current design) or shown with a clear
   "unverified — under review" banner so the tracker doesn't appear to omit known threats?
6. **Cost ceiling.** With opus on two of four layers plus web search per record, what's the expected
   per-run cost at, say, 30 threats, and does the daily cadence need to drop to weekly?

## 12. World Pulse (events) — the second content type

Added after the original blueprint above; kept intentionally short because the design principle is
**reuse, not fork**. Full rationale is in the status callout at the top of this document.

**Why a second schema, not a repurposed threat record:** a threat is a standing, assessment-based
risk (`probability × severity`); an event is a discrete, dated occurrence (an earthquake, an
outbreak, a displacement crisis) with a location, a status, and impact figures. Forcing an event into
`assessment.probability` would be dishonest — a past earthquake doesn't have an annual probability.

**What's shared, unchanged:** `claims[]`, `verification`, `provenance`, `last_updated`,
`schema_version` — byte-identical property definitions in `event.schema.json` and
`threat.schema.json`. `verify.apply_gate` (the trust core) needed **zero code changes**: it only
reads `record["claims"]`, so it is naturally kind-agnostic. `store.write_atomic`, `models.dumps`,
`models.stamp_provenance`, and `config.allowlisted`/`SOURCE_ALLOWLIST` are reused verbatim too.

**What's generalized with a `kind` parameter** (default `"threat"`, so the original path is
untouched): `schema.validate`, `store.write_record`/`dirs_for`/`load_all`,
`optimize.compute_sort_keys`, `curate.finalize`/`write`, `models.index_of`. Each dispatches on `kind`
to the right schema file / directory pair / rank computation.

**The `event` domain block** (replacing `assessment`): `occurrence_date`, `location {country, region}`,
`status (ongoing|contained|resolved)`, `scale` (free text — one field handles "M6.3", "Category 4",
and "PHEIC" alike), `impact {deaths, displaced, summary}`, `live_source_url` (the authoritative page
that keeps updating; the frontend links it as "live at source", with the cached figures explicitly
labeled "as of `<claims' retrieved_date>`" — never claimed as live itself). `location.lat`/`lon` and a
separate numeric `magnitude` field were deliberately **cut** after a review found them required but
always-null and read by nothing — premature groundwork for a map feature that doesn't exist; `scale`
already carries the same information as free text.

**Sort order inverts on purpose:** threats sort severity-dominant (a civilizational risk always
outranks a regional one, probability breaks ties). Events sort **recency-dominant**
(`recency_rank*10 + impact_rank` — today's earthquake outranks last month's flood, impact breaks
same-day ties) — a pulse is about *now*, not about *worst*.

**Allowlist additions for event sourcing:** `gdacs.org` (GDACS, the UN/EU disaster alert system),
`reliefweb.int` (ReliefWeb, UN OCHA's humanitarian reporting service), `imf.org` (for the `economic`
category). Same allowlist, same gate, same justification-comment convention as the original list.

**The "no ordinary news" filter is structural, not a prompt instruction:** an event only publishes if
a headline claim cites an allowlisted authoritative domain (USGS, WHO, GDACS, ReliefWeb, UN, …).
Routine politics, markets, sport, and celebrity news have no such primary document to cite, so they
fail the gate the same way an unsourced threat claim would — the "major event" bar in
`refresh-events.md` narrows *what's worth researching*, but the gate is what actually enforces it.

**Cadence and the trigger gap:** events refresh daily, threats weekly — both via a Claude Code on the
web scheduled trigger the user configures outside any coding session (not yet done as of this
writing; see `docs/BACKLOG.md`). Events auto-publish with no PR (an explicit decision: there's no
human in a daily unattended loop); threats still open a PR. A frontend staleness banner
(`frontend/app.js`) is the mechanism-agnostic safety net if a configured trigger silently stops.

---

*This is a design document. The next step is review/cross-verification; implementation is a separate,
separately-approved round.*
