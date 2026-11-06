# Design and refresh integration (November 2026)

The map-led frontend reads `frontend/data/events.json`, `threats.json`, and
`historical.json` with cache revalidation. No data snapshot is embedded in HTML.
`scripts/build_frontend.py` and the daily publisher still own these aggregates.
The UI renders published records only. Under-review records remain in their aggregate
for inspection but are not presented as published events. `#pulse` and `#history`
links continue to resolve alongside the new `#events` and `#historical` routes.

The flat map uses the existing self-hosted NASA image and source coordinates, with
approximate point locations rather than affected-area boundaries. Its legend describes
recorded-death buckets, unknown values and source attribution. History bounds expand
with incoming records; explicit ongoing ranges extend to the current UTC year.
Full descriptions, distinct impact/assessment context, source evidence, original live
source links and recorded update histories remain available on detail pages.

Response links are deliberately curated by event ID in `frontend/app.js`; country
matches do not establish aid relevance. Four official organization response pages
were checked on November 4, 2026. Links are not efficacy rankings or endorsements.
Missing matches stay explicit. The small organization marks are neutral initials,
not official logos. Review links and their scope periodically; daily data generation
does not verify these manually curated destinations.

Feedback prepares a GitHub issue URL. The visitor reviews and submits it on GitHub
and receives the issue URL there. No token, server, auto-submission or private inbox
is involved. The optional tracking field validates URL shape, not issue existence.

## Refresh and deployment checks

The documented external Claude routines are daily events at 09:00 UTC and weekly
risks on Monday at 10:00 UTC. The risk routine rotates records; one fresh batch does
not mean every risk was re-researched. History is updated ad hoc. The routine settings
were not accessible in the review browser without sign-in. Successful November 3–4
publish and Pages runs, and November 4 record/retrieval changes, demonstrate recent
operation rather than proving future runs or independently verifying all facts.

`publish.yml` accepts only its existing data allowlist and now validates the merged
main tree before pushing. `pages.yml` runs lint, tests, schema validation and aggregate
integrity checks before upload, so a separate green validate job is not assumed.
Do not hand-edit generated aggregates or include frontend code in a daily data branch.

`staleness.yml` invokes `scripts/check_freshness.py --live` daily at its existing
13:00 UTC schedule, and after a successful `pages` run on `main`. The post-deploy
check uses the Pages run's commit, so a newer main tip cannot create a false mismatch.
Failed Pages runs retain their own failure and do not launch another live freshness check.
Only the `pages` completion triggers this listener, so `staleness`/`notify` cannot loop.
It checks collection age (events 2 days, risks 10), every ongoing
event's edit age (2 days), and equality of live Pages data with the checked-out main
aggregates. Missing/invalid dates, stale ongoing records, failed fetches and deployment
mismatches fail the job. The check does not infer factual currency from edit dates.
A concurrent deployment can produce a transient mismatch; inspect the deploy and rerun.
The browser also warns about stale event/risk collection dates.

Before publication, the merged data tree gets a non-blocking `--report-only` freshness
preflight. It prints stale records and writes an incomplete-coverage job summary without
holding back valid updates to other records. The refresh command also asks for a per-event
coverage report. This never changes data, extends freshness thresholds, or claims a source
was read. The daily and post-deploy checks omit `--report-only`, so they still fail on
stale data, invalid dates, failed live fetches and deployment mismatches.

A failing scheduled check is a GitHub-native bridge for an external routine that stops
publishing. Email depends on the workflow actor and their Actions notification settings;
this repository cannot guarantee delivery or configure those settings. GitHub schedules
can be delayed or disabled. Automatic Telegram notifications were removed on November 6,
2026: unset Telegram secrets must not create a second failure for each genuine workflow
failure. `notify.yml` retains only an explicit manual self-test, which posts a real message
when configured and fails visibly if credentials or delivery are unavailable. A successful
self-test does not enable automatic Telegram alerts. No notification test, credentials or
subscriptions were created or changed by this update.

## Validation

Run `ruff check .`, `pytest -q`, `node --test tests/test_retrieval_ui.cjs`,
`python scripts/validate_data.py`, and `python scripts/build_frontend.py`.
Generated data must match the records. UI tests use current aggregates and cover complete
event text, retrieval provenance, safe links, loader behavior, dynamic history ranges,
and original-source/update access. Browser checks still matter for responsive layout,
map controls, carousel and navigation; physical touch-device testing is not automated.

Remaining pipeline limitation: the existing global publish concurrency group can cancel
an older pending run when several data branches arrive together. Shared CHANGELOG edits
can also conflict. Neither occurred during this release (only main existed); inspect
leftover claude/* branches after failures. This release does not automatically merge
or rewrite unrelated abandoned branches. A sweep/retry policy needs separate testing.
