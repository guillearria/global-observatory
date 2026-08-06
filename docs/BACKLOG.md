# Backlog

Known gaps and next iterations, roughly priority-ordered. Items marked *(Done)* are kept briefly
for context and pruned once uninteresting.

## State as of 2026-08-01

Everything below landed on `main` that day and is verified green: `validate` (first green run on
`main` since 2026-07-11) and `staleness` (green after 32 consecutive failures).

The day's work started from two red workflows and ended with the PR step removed everywhere:

1. **`validate` was red because of dependency drift, not any change.** `pyproject.toml` declared
   `ruff>=0.6` unbounded with no explicit rule selection, so CI floated to ruff 0.16.0, whose
   widened defaults produced 16 errors on a data-only PR. `main` was lint-broken too, unnoticed for
   five days. Fixed by pinning `ruff>=0.16,<0.17` **and** declaring `[tool.ruff.lint] select` — the
   pin alone would not have been enough, since the drift was in what the defaults *meant*.
2. **`staleness` was red because it was correct.** Threat data was 21 days old because the weekly
   refresh opened PRs nobody merged. The alarm was working; the review queue was not.
3. **The PR step is gone for all curated data**, including the source allowlist (see below).

### Trust-model change — the allowlist became agent-editable (2026-08-01)

`SOURCE_ALLOWLIST` moved from `pipeline/config.py` to `data/source-allowlist.json`, and refresh runs
may now extend it. **This is a real reduction in the trust guarantee and should be re-examined, not
inherited unquestioned.** Previously an agent could only cite domains a human had vetted; now it can
add a domain and then cite it, so "every published figure is grounded in an authoritative source" is
a claim the system makes about itself.

The mitigations actually in place, so a future session can judge whether they held rather than
rediscovering the decision:

- Only the allowlist **data** auto-publishes. `data/schema/` and `pipeline/` remain out of the
  `publish` scope, so a run can add a domain but never loosen the rules that check it.
- `data/schema/source-allowlist.schema.json` requires a bare hostname, a category from a fixed enum,
  and a `justification` past a length floor. `scripts/validate_data.py` gates the file and rejects
  duplicate domains.
- `pipeline/changelog.py` lists every newly allowlisted domain in `CHANGELOG.md`.
- The refresh commands require the **institution's own domain** — never an aggregator or news
  outlet — and require the addition to be called out in the run's final summary.

**Know exactly what the mitigations do and do not catch.** Verified by trying it: a malformed entry
fails the gate — a thin justification, a duplicate domain, a URL where a hostname belongs, a
category outside the enum. But a *well-formed* entry for a domain that is not an institution
(`newsaggregator.example`, with a plausible justification) passes every mechanical check. The
"institution's own domain, never an aggregator" rule lives only in the refresh command prompts, so
it constrains a cooperative agent and nothing else. That gap is the real residual risk, not
malformed JSON.

**What to check later:** whether any domain has actually been added, and whether its justification
holds up. `git log -p -- data/source-allowlist.json` is the whole history, and `CHANGELOG.md` lists
additions per commit. If additions turn out to be sloppy, the cheapest correction is not restoring
PRs but tightening the schema — an institutional-TLD constraint, or a cap on additions per commit,
either of which would move the aggregator rule from prompt to enforcement.

## Done — threats auto-publish is verified end-to-end

**Verified 2026-08-03**: the weekly threats routine ran on branch
`claude/trusting-archimedes-rv3fpc`, `publish` merged it to `main` and the record landed
(`9335d52`, adding `space-debris-kessler-syndrome`). The PR-review step it replaced was removed on
2026-08-01 after failing in exactly the way a review queue fails: the routine opened PRs #12, #13
and #14 on three consecutive Mondays, nobody merged them, `frontend/data/threats.json` went 21 days
stale, and — because each run listed existing slugs from `main` only — the same record was
re-proposed three times under different slugs (`geomagnetic-storm` → `severe-` → `extreme-`).
All three datasets now flow through `.github/workflows/publish.yml`.

## Operations — the refresh schedule

Both refresh routines are configured as Claude Code scheduled cloud agents (managed at
claude.ai/code/routines):

Both auto-publish the same way: the session pushes its own `claude/*` branch and
`.github/workflows/publish.yml` merges it to `main` after re-validating schema + a data-only diff +
byte-exact aggregates.

1. **World Pulse daily refresh** — daily 09:00 UTC → `/refresh-events`. *(Verified end-to-end
   2026-07-02.)*
2. **Existential threats weekly refresh** — Mondays 10:00 UTC → `/refresh-threats`. *(Verified
   end-to-end 2026-08-03.)*

Both prompts tell the agent to `pip install -e ".[dev]"` first and to stop — not publish — if
validation or tests fail. If a routine silently stops, the frontend's staleness banner
(events >2 days / threats >10) and the scheduled `.github/workflows/staleness.yml` check are the
signals.

**Known gap — a conflicted publish loses that day's refresh silently.** `publish` merges the
session branch into `main` and lets a conflict fail the job loudly, which is the right default: two
sessions editing the same record is not something to auto-resolve. But "loudly" only means a red
run nobody is watching. Staleness bounds the damage — a sustained outage still trips the >2-day
check — but a single lost run passes unnoticed. Worth fixing: the `frontend/data/*.json` conflicts
are spurious (the aggregates are derived and could simply be rebuilt post-merge), which would leave
only genuine record-level conflicts to fail on. Have the refresh commands `git pull --rebase` onto
current `main` before pushing, too.

**Audited 2026-08-05 — five abandoned branches, but two different failure modes.** A sweep of
`origin/claude/*` found five branches the routines left behind, and it is worth keeping them
straight because only one class is still possible today:

- **Three were the PR queue, not a conflict.** `trusting-archimedes-t109kw` (07-13),
  `-h17mg9` (07-20) and `-vhto1g` (07-27) are exactly PRs #12, #13 and #14 — opened by the weekly
  threats routine, never merged, closed when auto-publish replaced the queue on 08-01. This is the
  failure already described under "Done — threats auto-publish" above, and `publish` fixed it.
- **Two were the events routine's push.** `trusting-wright-ls09pf` (07-13) is the conflicted
  publish described above; `trusting-wright-cyb9hp` (07-21) carried no record changes at all. So
  the conflict mode has cost one run in ~30, as originally recorded — that count was right.

What the audit did change: **two threat records were drafted twice and never published at all** —
`antimicrobial-resistance` and the major-earthquake record, lost with PRs #12 and #13, salvaged and
re-verified against live sources in `1896754`. No threat record reached `main` between 07-11 and
08-01.

**The detector worked; nobody was listening.** `staleness` failed on 11 consecutive days, 07-22
through 08-01 — exactly on schedule, 10 days after the last threats landing on 07-11 — and the
queue still sat undrained until the auto-publish rewrite happened to fix it. This is the real
finding of the audit, and it is not a missing check:

- Every alarm this repo has is a **red CI run**, and a red CI run is only a signal if a human is
  subscribed to it. `staleness.yml`'s own header says it notifies "the last committer" — but under
  auto-publish the last committer is `global-observatory-publisher`, a bot. The louder the
  automation got, the quieter the alarm became.
- So the gap to close is **notification, not detection**. Something has to leave GitHub — the HQ
  Telegram path already used for publish approvals is the obvious carrier.
- Worth adding regardless, because it is the one unambiguous failure signature and it is cheaper
  than inferring failure from data freshness: **alarm on any `claude/*` branch older than ~24h.**
  `publish` deletes the branch on success, so a lingering branch always means a run did not land.
  It would have caught all five of these on the day they happened.

**Related, same root cause — the changelog was silently corrupted.** `pipeline.changelog` is a
projection of `git log --name-status` over the data dirs, so it is only as correct as the history
it can see. Regenerated inside a shallow sandbox clone, the graft boundary looks like the commit
that created every file: the committed `CHANGELOG.md` credited `c78618a` (a CHANGELOG-only commit)
with adding all 62 records, and had lost the 21 real entries for the commits that actually made
those changes. Repaired in `d511af8` by regenerating from full history. Regenerating a
history-derived artifact anywhere but on complete history should be treated as unsafe.

### Deliberate choices — do not "finish the job" by reverting these

Three things look like leftovers from the PR era but are intentional:

- **`validate.yml` keeps its `pull_request:` trigger.** No dataset uses PRs any more, but the
  trigger costs nothing and is the only CI an outside contributor's PR would ever get. Removing it
  would silently make drive-by contributions unvalidated.
- **`data/schema/` stays out of the `publish` scope**, even though `data/source-allowlist.json`
  next to it auto-publishes. That asymmetry is the whole safety property: a refresh run can add a
  trusted domain but can never edit the rules that check one.
- **`validate.yml` also needs its `workflow_dispatch:` trigger**, because `publish.yml`'s last step
  dispatches it explicitly after each auto-merge. Deleting the trigger would break that step and
  return `validate` to never running on `main`.

## Housekeeping — small, known, not yet done

- **Five orphaned remote branches.** `claude/trusting-archimedes-{t109kw,h17mg9,vhto1g}` (the closed
  threat PRs #12/#13/#14) and `claude/trusting-wright-{cyb9hp,ls09pf}` (leftover events runs, one of
  them the conflicted 2026-07-13 publish above). Deleting them failed from the cloud session — the
  git proxy rejects delete refspecs with `send-pack: unexpected disconnect` — so they need removing
  from a local clone or the GitHub UI. Worth doing rather than ignoring: the refresh commands now
  tell each run to inspect leftover `claude/*` branches before drafting, so stale ones actively
  mislead.
- **The ruff pin needs a human bump eventually.** `ruff>=0.16,<0.17` stops the drift that broke CI,
  but nothing adopts 0.17 on its own. When bumping, expect new findings and treat them as the pin
  having done its job — not as a regression.
- **`changelog.regenerate()` is not deterministic across clones.** Regenerating on a clean `main`
  already produces a diff against the committed `CHANGELOG.md`: older entries get re-attributed to
  different commits depending on the clone's graph. Pre-existing, cosmetic, and unchecked by CI, but
  it means "regenerate and commit" always churns beyond the new entry.
- **The 2026-07-27 threat claims were verified by reading, not refetching.** The cloud session that
  landed them had an egress policy blocking `noaa.gov`, `nasa.gov` and `ipcc.ch` (403 at the CONNECT
  tunnel), so the cited pages could not be re-opened. They were accepted because every claim is
  anchored to a closed period — a June 2026 monthly mean, the 2025 annual ranking, an 1859 event, a
  February 2025 probability peak — none of which five days of age can falsify. A refresh routine
  running in its own cloud session has different egress and re-verifies them normally.

## Trust & verification

- **Semantic entailment check**: today the gate confirms an authoritative source was *cited*, not
  that it supports the claim. Add a skeptic pass to the refresh commands asked to *refute* each
  claim against its cited page; quarantine on refutation.
- **Citation rot / archival**: no Wayback/archival snapshot. A dead link currently just downgrades
  to unverified on the next refresh; consider archiving the retrieved page. Applies to all three
  kinds — historical claims especially, since scholarly pages move.

## Frontend & delivery

- **Richer UI**: category/event-type filtering, search, surfacing each claim's quoted supporting
  passage, a clearer verified/partial distinction, and a small legend for the trust badges. For the
  Historical Archive: century sub-grouping or filtering once the timeline grows past ~60 records.
- **World Pulse map/lat-lon** *(Done 2026-07-05 — optional `lat`/`lon` landed in the event schema
  with the map as their consumer: a self-contained NASA Blue Marble basemap in `frontend/map.js`
  with pan/zoom and impact-scaled markers. All four events carry coordinates; `/refresh-events`
  now asks for them.)*
- **Map: Leaflet upgrade path**: the static basemap softens past ~6× zoom. If street-level detail
  is ever wanted, swap `map.js` for vendored Leaflet + Esri World Imagery tiles behind the same
  two-method `GOMap` API — decided against for now to keep the zero-external-requests property.
  Marker clustering becomes worth it if the pulse ever tracks dozens of co-located events.
- **Secondary staleness monitoring** *(Done — `.github/workflows/staleness.yml` fails loudly when
  the committed aggregates go stale, complementing the client-side banner. The Historical Archive
  is deliberately exempt.)*

## Data

- **Fill the empty threat categories** *(Done 2026-07-02 — all 8 categories now have at least one
  record; nuclear needed a SIPRI allowlist entry since IAEA publishes no arsenal counts.)*
- **Flip the forced-displacement headline claim to verified**: the record is honestly `partial`
  because claim-1's 117.8M end-2025 total can't be machine-confirmed — unhcr.org 403s automated
  fetchers (curl and WebFetch alike), its Wayback playback is a JS shell with no figures, and the
  allowlisted mirrors (UN News story, UNifeed briefing) carry only the 41.6M refugee component.
  Search-result snippets do corroborate 117.8M from Global Trends (June 2026), but the trust rule
  requires confirming the figure on the cited page. A human with a real browser: open
  https://www.unhcr.org/global-trends, confirm the total, set claim-1 `verified` with today's
  `retrieved_date`, and re-run it through `curate.write(kind="threat")`.
- **Seed more real events**: more accrue naturally once the daily routine is running; no action
  needed beyond that.
- **Seed the Historical Archive** *(Done 2026-07-06 — 43 landmark records across all six eras,
  researched against allowlisted sources and gated; 41 verified, 2 honest-partial. Grow it further
  via `/refresh-history`.)*
- **Economic coverage — the one thin spot, across all three features.** Economic crises are
  under-represented everywhere, and this is a single gap to close in three places:
  - *Historical Archive*: the seed batch has no `economic` records. Add the landmark ones via
    `/refresh-history` — e.g. the 1929 crash / Great Depression, the 1997 Asian financial crisis,
    the 2008 global financial crisis, hyperinflations (Weimar 1923, Zimbabwe 2007-09). Sources are
    already allowlisted (IMF, World Bank, OECD, europa.eu, un.org).
  - *World Pulse*: the `economic` event category and the IMF/World Bank/OECD allowlist entries
    already exist, so **the daily read can and should capture a major market crash or financial
    crisis the day it happens** — a systemic shock (a >~20% index collapse, a sovereign default, a
    banking crisis, an IMF/central-bank emergency intervention), not routine market movement.
    `/refresh-events` was clarified (2026-07-06) to put this in scope; watch that the daily routine
    actually surfaces one when it occurs.
  - *Existential Threats*: consider whether a standing `societal`/`economic` systemic-financial-risk
    record belongs alongside the others (global debt, a systemic banking collapse). Lower priority
    than the above two.

## Tooling

- **Python version**: `requires-python` is `>=3.11`; CI runs 3.12. Revisit if any 3.12-only
  feature is wanted.
