# Backlog

Known gaps and next iterations, roughly priority-ordered. Items marked *(Done)* are kept briefly
for context and pruned once uninteresting.

## Next up — verify threats auto-publish end-to-end

**The weekly threats routine now auto-publishes; its first run under the new `publish` workflow is
unverified.** The PR-review step was removed on 2026-08-01 after it failed in exactly the way a
review queue fails: the routine opened PRs #12, #13 and #14 on three consecutive Mondays, nobody
merged them, `frontend/data/threats.json` went 21 days stale, and — because each run listed
existing slugs from `main` only — the same records were re-proposed three times under different
slugs (`geomagnetic-storm` → `severe-` → `extreme-`). All three datasets now flow through
`.github/workflows/publish.yml`. Watch the next Monday run: the `claude/*` branch should be
auto-merged and deleted, with `pages` and `validate` dispatched afterward.

## Operations — the refresh schedule

Both refresh routines are configured as Claude Code scheduled cloud agents (managed at
claude.ai/code/routines):

Both auto-publish the same way: the session pushes its own `claude/*` branch and
`.github/workflows/publish.yml` merges it to `main` after re-validating schema + a data-only diff +
byte-exact aggregates.

1. **World Pulse daily refresh** — daily 09:00 UTC → `/refresh-events`. *(Verified end-to-end
   2026-07-02.)*
2. **Existential threats weekly refresh** — Mondays 10:00 UTC → `/refresh-threats`. *(Auto-publish
   path not yet verified — see "Next up" above.)*

Both prompts tell the agent to `pip install -e ".[dev]"` first and to stop — not publish — if
validation or tests fail. If a routine silently stops, the frontend's staleness banner
(events >2 days / threats >10) and the scheduled `.github/workflows/staleness.yml` check are the
signals.

**Known gap — a conflicted publish loses that day's refresh silently.** `publish` merges the
session branch into `main` and lets a conflict fail the job loudly, which is the right default: two
sessions editing the same record is not something to auto-resolve. But "loudly" only means a red
run nobody is watching. This has happened once in 30 daily runs (2026-07-13, branch
`claude/trusting-wright-ls09pf` — conflicts in `ebola-bundibugyo-drc-2026`,
`typhoon-bavi-guam-mariana-2026`, `events.json` and `CHANGELOG.md`, because the sandbox had cloned
`main` before an earlier run landed); that day's updates were never published and the branch is
still sitting unmerged. Staleness bounds the damage — a sustained outage still trips the >2-day
check — but a single lost day passes unnoticed. Worth fixing: the `frontend/data/*.json` conflicts
are spurious (the aggregates are derived and could simply be rebuilt post-merge), which would leave
only genuine record-level conflicts to fail on. Have the refresh commands `git pull --rebase` onto
current `main` before pushing, too.

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
