# Backlog

Known gaps and next iterations, roughly priority-ordered. Items marked *(Done)* are kept briefly
for context and pruned once uninteresting.

## Operations — the refresh schedule

Both refresh routines are configured as Claude Code scheduled cloud agents (managed at
claude.ai/code/routines):

1. **World Pulse daily refresh** — daily 09:00 UTC → `/refresh-events` (auto-publishes through
   the gate, pushes to `main`).
2. **Existential threats weekly refresh** — Mondays 10:00 UTC → `/refresh-threats` (opens a PR
   for human review).

Both prompts tell the agent to `pip install -e ".[dev]"` first and to stop — not push / not open
the PR — if validation or tests fail. If a routine silently stops, the frontend's staleness banner
(events >2 days / threats >10) and the scheduled `.github/workflows/staleness.yml` check are the
signals.

## Trust & verification

- **Semantic entailment check**: today the gate confirms an authoritative source was *cited*, not
  that it supports the claim. Add a skeptic pass to the refresh commands asked to *refute* each
  claim against its cited page; quarantine on refutation.
- **Citation rot / archival**: no Wayback/archival snapshot. A dead link currently just downgrades
  to unverified on the next refresh; consider archiving the retrieved page. Applies to both threats
  and events.

## Frontend & delivery

- **Richer UI**: category/event-type filtering, search, surfacing each claim's quoted supporting
  passage, a clearer verified/partial distinction, and a small legend for the trust badges.
- **World Pulse map/lat-lon**: `location.lat`/`lon` were deliberately cut from the event schema as
  premature (required-but-always-null, no consumer). Revisit only if a real map view is wanted —
  re-add as optional fields and wire an actual consumer first.
- **Secondary staleness monitoring** *(Done — `.github/workflows/staleness.yml` fails loudly when
  the committed aggregates go stale, complementing the client-side banner.)*

## Data

- **Fill the empty threat categories** (nuclear, technological, resource, societal): in progress —
  seeded via `/refresh-threats` runs; nuclear needed a SIPRI allowlist entry since IAEA publishes
  no arsenal counts.
- **Seed more real events**: more accrue naturally once the daily routine is running; no action
  needed beyond that.

## Tooling

- **Python version**: `requires-python` is `>=3.11`; CI runs 3.12. Revisit if any 3.12-only
  feature is wanted.
