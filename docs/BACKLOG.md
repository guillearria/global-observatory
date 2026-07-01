# Backlog

Post-MVP work, captured during the first-draft build. The MVP is intentionally rough; this is the
list of known gaps and next iterations. Roughly priority-ordered.

## Next up — the actual resumption point

Everything code-side for World Pulse (daily events) is built, tested, and manually verified
end-to-end (see `docs/ARCHITECTURE.md` §12). **The one remaining step is external and must be done
by a human in the Claude Code on the web dashboard** (not from inside a coding session):

1. **Daily trigger** → prompt: `/refresh-events` (or "run the /refresh-events slash command on
   guillearria/end-times-tracker"), pointed at this repo, with write access.
2. **Weekly trigger** → prompt: `/refresh-threats`, same repo, same access.

Until both are configured, the dataset only refreshes when someone runs one of those commands
manually. The frontend's staleness banner (`frontend/app.js`, events >2 days / threats >10) is the
signal to watch for — if it lights up, either a trigger isn't configured yet or one has silently
stopped firing.

## Trust & verification
- **Semantic entailment check** (ARCHITECTURE.md §11 #1): today Verify confirms an authoritative
  source was *cited*, not that it supports the claim. Add a second skeptic call asked to *refute*
  each claim; quarantine on refutation.
- **Harden + test live citation extraction** (`verify._extract_citations`): it is best-effort and
  untested against real API responses. Add fixtures captured from a real run and unit-test the
  list-vs-error-object branching and citation-block shapes.
- **Expand the source allowlist** for `technological` (AI risk) and `societal` (ARCHITECTURE.md §11
  #2): these categories will tend to quarantine until more authoritative domains are added. NIST is
  the only technological anchor right now. *(Done — added UK AISI, OECD.AI, ITU for technological and
  OHCHR, UNHCR, UNESCO, WFP, EU/europa.eu for societal/resource; see `config.SOURCE_ALLOWLIST`.)*
- **Citation rot / archival** (ARCHITECTURE.md §10): no Wayback/archival snapshot. A dead link
  currently just downgrades to unverified on the next run; consider archiving the retrieved page.
  Applies equally to World Pulse events now that they exist.

## Pipeline
- **Confirm Correction #1**: run `scripts/probe_haiku.py` against the live API; if Haiku accepts
  adaptive thinking, remove it from `config.NO_ADAPTIVE_THINKING`.
- **Cross-threat merge** (`_merge_into`): Clean-up's model-proposed merges are not implemented;
  `merge_proposals` only dedups by slug. Decide whether to keep this out of scope or implement the
  deterministic merge executor.
- **Optimize text-tightening is live-only**: the prose pass runs only with an API key; dry-run just
  computes `sort_keys`. Fine, but note the dry frontend won't show optimized prose.
- **Cost cadence** (ARCHITECTURE.md §11 #6): measure per-run cost after the first live `--only-slug`
  and decide whether daily stays viable or drops to weekly. Consider batch API / prompt caching (both
  explicitly deferred in the MVP). *(In progress — per-call token/cost logging now lands in the run
  summary via `client.usage_summary()` + `config.estimate_cost()`; the daily-vs-weekly decision is
  pending real numbers from the first live `--only-slug` run.)*

## Frontend & delivery
- **GitHub Pages deploy workflow** *(Done — `.github/workflows/pages.yml` publishes `frontend/` on
  every push to `main` touching `frontend/**`.)*
- **Richer UI**: category/event-type filtering, search, surfacing each claim's quoted supporting
  passage, a clearer verified/partial distinction, and a small legend for the trust badges. Now
  applies to both panes.
- **World Pulse map/lat-lon** (ARCHITECTURE.md §12): `location.lat`/`lon` were deliberately cut from
  the event schema as premature (required-but-always-null, no consumer). Revisit only if a real map
  view is wanted — re-add as optional fields, not required, and wire an actual consumer before adding
  the Python range-check machinery back.
- **Secondary staleness monitoring** (considered, deferred): a $0 GitHub Actions job that fails
  loudly if `frontend/data/*.json`'s `last_updated` goes stale, as a belt-and-suspenders complement to
  the frontend banner. Skipped for now per "don't over-engineer" — add only if the banner alone proves
  insufficient once the scheduled triggers are live.

## Data
- **Seed more real threats** *(Done — `global-warming`, `influenza-pandemic`, and
  `near-earth-asteroid-impact` were added alongside the original `yellowstone-supervolcano`.)*
- **Seed more real events**: only 3 World Pulse events exist (Venezuela earthquake, DRC/Uganda Ebola
  PHEIC, Sudan displacement crisis). More will accrue naturally once the daily trigger is running;
  no action needed beyond that.

## Tooling
- **Python version**: `requires-python` is `>=3.11` so it runs in the current dev environment; the
  blueprint targets 3.12 and CI runs 3.12. Revisit if any 3.12-only feature is wanted.
