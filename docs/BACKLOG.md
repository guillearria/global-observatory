# Backlog

Known gaps and next iterations, roughly priority-ordered. Items marked *(Done)* are kept briefly
for context and pruned once uninteresting.

## Next up — the one untested path

**The weekly threats routine's first scheduled run (Monday 10:00 UTC → `/refresh-threats`) has
never executed in the cloud.** The daily events path was verified end-to-end on 2026-07-02
(research → gate → session branch → `publish-events` merge → deploy), but the threats path differs
in its last step: the cloud session pushes its `claude/*` branch (correctly skipped by
`publish-events`, since it touches threat data) and must then open a PR. Whether the sandbox can
open the PR itself is unverified — watch Monday's run; if the branch appears without a PR, open it
by hand and adjust the command/routine accordingly.

## Operations — the refresh schedule

Both refresh routines are configured as Claude Code scheduled cloud agents (managed at
claude.ai/code/routines):

1. **World Pulse daily refresh** — daily 09:00 UTC → `/refresh-events`. Auto-publish: the session
   pushes its own `claude/*` branch and `.github/workflows/publish-events.yml` merges it to `main`
   after re-validating schema + an events-only diff. *(Verified end-to-end 2026-07-02.)*
2. **Existential threats weekly refresh** — Mondays 10:00 UTC → `/refresh-threats` (opens a PR
   for human review; see "Next up" above).

Both prompts tell the agent to `pip install -e ".[dev]"` first and to stop — not publish — if
validation or tests fail. If a routine silently stops, the frontend's staleness banner
(events >2 days / threats >10) and the scheduled `.github/workflows/staleness.yml` check are the
signals.

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
  record; nuclear needed a SIPRI allowlist entry since IAEA publishes no arsenal counts. The
  forced-displacement record is honestly `partial`: unhcr.org blocks automated fetchers, so its
  headline total is marked unverified — flip it to verified by confirming the figure in a browser.)*
- **Seed more real events**: more accrue naturally once the daily routine is running; no action
  needed beyond that.
- **Seed the Historical Archive**: the kind, schema, gate wiring, and timeline UI shipped
  2026-07-05 with an empty dataset. Seed ~40 landmark records (pandemics, wars, famines, disasters,
  collapses across all six eras) via `/refresh-history` — PR-reviewed like threats.

## Tooling

- **Python version**: `requires-python` is `>=3.11`; CI runs 3.12. Revisit if any 3.12-only
  feature is wanted.
