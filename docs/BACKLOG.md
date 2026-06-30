# Backlog

Post-MVP work, captured during the first-draft build. The MVP is intentionally rough; this is the
list of known gaps and next iterations. Roughly priority-ordered.

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
- **GitHub Pages deploy workflow**: add a `pages.yml` that publishes `frontend/` after each data
  commit so the static site goes live.
- **Richer UI**: category filtering, search, surfacing each claim's quoted supporting passage,
  a clearer verified/partial distinction, and a small legend for the trust badges.

## Data
- **Seed more real threats**: the repo ships only the hand-authored Yellowstone record. Add a few
  more genuinely-sourced records (nuclear, biological, climate) so the first deploy isn't near-empty.

## Tooling
- **Python version**: `requires-python` is `>=3.11` so it runs in the current dev environment; the
  blueprint targets 3.12 and CI runs 3.12. Revisit if any 3.12-only feature is wanted.
