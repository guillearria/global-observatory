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
only genuine record-level conflicts to fail on. *(Narrowed 2026-08-16 — all three refresh commands
now rebase onto current `main` immediately before pushing, rebuilding the derived aggregates on a
spurious conflict and stopping loudly on a real `data/**` one. The publish-side rebuild remains
open.)*

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
  subscribed to it. `staleness.yml`'s own header said it notifies "the last committer" — but under
  auto-publish the last committer is `global-observatory-publisher`, a bot. The louder the
  automation got, the quieter the alarm became.
- So the gap to close is **notification, not detection**. Something has to leave GitHub.

**Fixed 2026-08-05 — `notify.yml` + `scripts/notify.py`.** One `workflow_run` listener on
`staleness`, `publish`, `validate` and `pages` pushes any failure to Telegram. See ARCHITECTURE §7
for the design and its one gap (a newly added workflow must be listed in its `workflows:` array).

> **Arming it is a manual step and it is silent until done.** The alarm needs two repository
> secrets, and until they are set it exits 0 with a notice — deliberately, so an unarmed notifier
> does not turn every failure into a second unwatched red run. Reuse the same bot as the other
> portfolio routines:
>
>     gh secret set TELEGRAM_BOT_TOKEN --repo guillearria/global-observatory
>     gh secret set TELEGRAM_CHAT_ID  --repo guillearria/global-observatory
>
> Then verify — **do not assume it works because CI is green**, since a notifier that was never
> armed looks exactly like one with nothing to report:
>
>     gh workflow run notify.yml --repo guillearria/global-observatory
>
> The self-test sends a message and, uniquely, **fails when the secrets are unset**. A silent skip
> is right when there is a real failure to report and wrong when a human is asking "is this armed?"
> — that question must never answer green without a message having gone out. A green self-test run
> plus a Telegram message is the only proof.

**Still unarmed as of 2026-10-15.** `gh secret list` shows no `TELEGRAM_*` secrets here, so the
2026-10-03 `publish` failure reached no one (harmless that time, since the day's refresh still
landed). swing-lab already holds both secrets, so arming this repo means reusing the same two
values. Steps went to the owner on 2026-10-15; replace this paragraph once the self-test is green.

**Still open — alarm on orphaned `claude/*` branches.** The one unambiguous failure signature, and
cheaper than inferring failure from data freshness: `publish` deletes the branch on success, so a
lingering branch always means a run did not land. It would have caught all five July casualties on
the day they happened, including the two that `staleness` could not see because other records kept
the aggregate fresh. Now that `notify.yml` exists, this is just a scheduled check that fails when
`git ls-remote --heads origin 'claude/*'` returns anything older than ~24h.

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

- **Orphaned remote branches.** A 2026-08-05 sweep found five (`claude/trusting-archimedes-*`,
  `claude/trusting-wright-*`); deleting them failed from the cloud session — the git proxy rejects
  delete refspecs with `send-pack: unexpected disconnect` — so they need removing from a local
  clone or the GitHub UI. Worth doing rather than ignoring: the refresh commands tell each run to
  inspect leftover `claude/*` branches before drafting, so stale ones actively mislead. A branch
  merged to `main` by hand also orphans its pointer (`publish` only deletes branches it merged
  itself) — `claude/world-pulse-ux-fixes-f8t81v` sat that way after b231d04; deleted from a local
  clone 2026-08-19, leaving no orphans outstanding.
- **The ruff pin needs a human bump eventually.** `ruff>=0.16,<0.17` stops the drift that broke CI,
  but nothing adopts 0.17 on its own. When bumping, expect new findings and treat them as the pin
  having done its job — not as a regression.
- **~~`changelog.regenerate()` is not deterministic across clones.~~ Resolved 2026-08-19 — the churn
  was corruption, not non-determinism.** The committed file had been regenerated from a *shallow*
  clone, where the graft-boundary commit looks like the one that added every tracked file; that
  flattened weeks of history into a single "Added" list and left 35 sections where the full graph
  yields 86. Every later regeneration from a complete clone therefore "churned" — it was repairing
  the damage. Repaired in `f14b999`; regenerating on a clean `main` from a full clone is now a
  no-op. **This has now happened twice** (see also `d511af8`, 2026-08-05), so treat future churn on
  a clean `main` as the signal that a shallow-clone regeneration got committed again — not as
  cosmetic noise. `git rev-parse --is-shallow-repository` must print `false` before regenerating.
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

- **Public copy: one message, one wording** *(owner, 2026-10-15; next up, with the site rework)*.
  The README and the GitHub About were rewritten in plain language on 2026-10-15. The About is
  the README's first sentence, word for word, and the technical material moved to
  [`TECHNICAL-OVERVIEW.md`](TECHNICAL-OVERVIEW.md). The site's own copy is next: the About tab,
  the section subtitles, `<meta name="description">` and `og:description`. Reuse the README's
  sentences rather than rewording them, so a reader meets the same message on GitHub and on the
  site. Keep the public terms consistent too: "the checking program" is the trust gate, "the
  approved list" is `data/source-allowlist.json`, and "Under review" is quarantine. Don't
  over-explain: the About is one sentence, and the README carries the explanation.
  **2026-10-20 (owner: "WAY too much verbosity"):** the README is now one screen; its full
  plain-language text moved word for word to [`HOW-IT-WORKS.md`](HOW-IT-WORKS.md). Reuse sentences
  from there for the site copy. The About is still the README's first sentence.
- **README screenshot of the map** *(deferred by the owner 2026-10-15)*. A screenshot near the
  top of the README would help lay readers, but the site may get a visual revamp soon. Do it
  once, after the revamp.
- **Custom domain** *(pending the owner's portfolio decision, 2026-10-15; do not implement
  until decided)*. `momo.rodeo` was registered 2026-10-14 and `arria.dev` is under
  consideration. The choice belongs to the portfolio as a whole, not to this repo. The changes
  on this side are small: three hardcoded URLs in `frontend/index.html` (canonical, `og:url`,
  `og:image`), the README's site link, and the repo's About website field. GitHub
  301-redirects the old `github.io` address to a custom domain, so existing links keep working.

- **Design pass — cards, identity chrome, detail view** *(Done 2026-08-26 — PRs #16, #17, #18;
  plan, audit and decisions in [`docs/DESIGN-PASS.md`](DESIGN-PASS.md)).* The identity brief HQ
  wrote here on 2026-08-24 shipped as Phase 2 — masthead with a globe-and-pulse mark, data-URI
  favicon, footer carrying the trust-gate sentence, Newsreader 600 self-hosted under
  `frontend/assets/fonts/` — after the owner's 2026-08-25 card feedback superseded its "do not
  restyle the event cards" line: Phase 1 gave all three tabs one card anatomy (dateline · title ·
  first-sentence teaser, whole card clickable, no ellipsis anywhere), and Phase 3 moved the heavy
  details — full location, scale, *live at source*, the gate's verdict in words — to the detail
  view. Decisions taken with the owner: D1 accent unchanged, D2 one self-hosted display face,
  D3 globe + pulse mark, D4 dateline yes, D5 quiet-verified / loud-exception, D6 no deaths range on
  archive cards, D7 teaser derived client-side rather than a schema field.

  **Round 2 (owner feedback, same day — one PR):** tagline and trust prose moved to a new
  **About** tab; dateline separators are pipes; event status sits on the right with the signal
  group; **verified is unlabelled** — a pill appears only on the exceptions (cards and citations
  alike); footer is swing-lab's *Project code on GitHub · Built by …*. The partial/verified
  distinction stays in the pipeline (it is what makes "thoroughly verified" checkable) but is no
  longer a list-surface label. See the plan's §9.

  **The unverified claims were a fetch problem, not an allowlist problem — four of five now
  closed in a real browser.** Five of 594 claims (0.8%) cited allowlisted domains that block
  automated fetchers; the gate never downgraded them, the curating sessions honestly left them
  `unverified`. Closed 2026-08-26, each confirmed verbatim with the quotation appended to the
  claim: UNHCR (`2fd54b4`), Britannica Aleppo 1138 and Yangtze 1931 (`b34a7dc`), ReliefWeb
  Tunisia wildfires (`a53c59e` — an IFRC situation report, originally published 30 Jul 2026).
  **The fifth closed too (`a547c24`, via `/refresh-history`):** `thirty-years-war` claim-3 had
  cited Britannica's brief event page, which states no toll. Re-sourced to Britannica's *Germany*
  article ("an overall population decline of 15 to 20 percent (from about 20 million to 16 or 17
  million)", Württemberg "more than 50 percent"), a Journal of Refugee Studies article (OUP:
  "deaths of an estimated 15-20 per cent of the population of the Holy Roman Empire") and a
  German History article (OUP) on how contested the figures are; the toll is now stated as the
  sources give it — 3–4 million as 15–20 per cent of ~20 million, explicitly an order of
  magnitude mixing deaths with flight — instead of the unsourced 4.5–8 million. **Every
  published record on the site is now fully verified; no `partial` pill appears anywhere.**

  **Round 4 (2026-08-26):** the masthead nav (Code · author) and the About sub-line went — both
  duplicated the About panels and the footer. Shipped from the follow-ups: `og:image` (a
  1200×630 render of the mark + wordmark in the site's own face, `assets/og-image.png`,
  `twitter:card summary_large_image`); **search on all three tabs** (every query word must
  appear in the name, description, place, category or date) plus a **category filter on World
  Pulse**; and the refresh prompt now says `region` and `scale` are labels, not prose. Not done,
  by design: an explicit `teaser` field — the derived first sentences read fine after the
  prompt steer (60–421 chars, zero fallbacks), so there is nothing to fix.

  Still open, recorded not scheduled:
  - **Explicit `teaser` field** only if a future refresh produces first sentences that read badly.
  - **Search over claim text** if readers want it — today search covers name, description,
    place, category and date, not citations.
- **Weekly email newsletter**: share each week's results by email — a digest of World Pulse
  changes (new events, major figure updates, resolved/contained transitions) plus any threat or
  archive additions. The diff source already exists: `CHANGELOG.md` is a projection of git history
  over the data dirs, so a "past 7 days" digest is derivable with no new bookkeeping. To evaluate:
  a scheduled GitHub Action that renders the digest and hands it to an email service, vs. a hosted
  newsletter tool (e.g. RSS-to-email) fed by a small generated feed. Open questions: subscriber
  storage and privacy (the repo must not hold addresses), and note the zero-external-requests
  property applies to the *site* — delivery infrastructure is a separate decision.
- **Richer UI**: category/event-type filtering, search, surfacing each claim's quoted supporting
  passage, a clearer verified/partial distinction, and a small legend for the trust badges. For the
  Historical Archive: century sub-grouping or filtering once the timeline grows past ~60 records.
  *(Partly done 2026-08-10 — the threats pane filters by category/severity and the archive sorts
  by date and filters by type. Partly done 2026-08-16 — compact three-badge cards with per-record
  detail views: full prose, key figures, the `updates[]` timeline, and always-expanded citations
  on `#pulse/<id>`-style routes. The trust-badge legend landed in the footer 2026-08-26; search
  remains.)*
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
- **Flip the forced-displacement headline claim to verified** *(Done 2026-08-26 — `2fd54b4`, via
  the publish workflow.)* Opened in a real browser: the page's prose gives the one-in-70 ratio and
  its 2025 chart data table gives the five components (67,228,580 IDPs, 28,461,306 refugees under
  UNHCR's mandate, 5,964,782 Palestine refugees, 8,998,091 asylum-seekers, 7,177,473 others in
  need of international protection), which sum to 117,830,232 — the claim text now records that
  derivation. Worth knowing for future refreshes: **the 117.8M total is not in the page's prose,
  only in the hidden `<table>` behind the chart**, so a text-only fetch never finds it.
- **Full `updates[]` logs were trimmed oldest-first** *(Fixed 2026-10-31.)* The DRC Ebola and
  Washington wildfire records reached the 30-entry cap (Ebola on 22 September, Washington on
  9 October) and the daily routine kept them at 30 by deleting the oldest entry each run. That cost
  Ebola about 20 entries, including
  the outbreak becoming DRC's largest ever, the spread to Bas-Uele, the Ervebo allocation and the
  end of Uganda's linked outbreak; Washington lost its 1 August state emergency and 4 August
  federal declaration. Both logs were condensed into monthly summaries with those milestones
  restored word for word from earlier published versions (each backed by a claim in the record).
  Ebola is now at 16 entries and Washington at 11. `author_event.py` now refuses a draft that drops
  entries unless `--condense` is passed, `validate_data.py` warns from 25 entries, and
  `/refresh-events` caps a running tally at one entry a week. Still near the cap and left for the
  routine to condense under the new rule: `canada-british-columbia-wildfires-2026` and
  `pakistan-floods-2026` (25 each).
- **Claims grow without a cap — the real driver of `events.json` size.** `frontend/data/events.json`
  passed 1 MiB on 2026-10-31 (1.07 MB, up ~190 KB a month) and claims are ~60% of it: a long-running
  record gains a new dated ECDC/InciWeb claim per figure change (Ebola has 75). Nothing is broken
  yet. Options when it matters: retire claims superseded by a newer reading of the same source page,
  or stop shipping old claims to the frontend. Either touches the trust model, so decide
  deliberately.
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
