# Backlog

Known gaps and next iterations, roughly priority-ordered. Items marked *(Done)* are kept briefly
for context and pruned once uninteresting.

## Next up — the actual resumption point

Everything code-side is built and tested. The remaining step is **scheduling the two refresh
routines** as Claude Code scheduled cloud agents:

1. **Daily** → run `/refresh-events` on this repo (auto-publishes through the gate, pushes to
   `main`). Prompt should tell the agent to `pip install -e ".[dev]"` first and to stop — not
   push — if validation or tests fail.
2. **Weekly** → run `/refresh-threats` (opens a PR for human review). Same setup line, same
   stop-on-failure rule.

Until both are live, the dataset only refreshes when someone runs a command manually. The
frontend's staleness banner (events >2 days / threats >10) and the scheduled
`.github/workflows/staleness.yml` check are the signals if a routine is missing or silently stops.

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
