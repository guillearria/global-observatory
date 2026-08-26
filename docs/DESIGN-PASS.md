# Design pass — implementation plan

**Status: IMPLEMENTED — Phases 1–3 merged 2026-08-26 as PRs #16, #17 and #18; Phase 4 (docs) closed it.**
Kept as the record of the audit, the decisions and the verification recipe. Written 2026-08-25
from three sources, reconciled:

1. **HQ's brief** — the identity-pass item at the top of `BACKLOG.md` → *Frontend & delivery*
   (commit `cdba4c7`): favicon, masthead, footer, optional `og:image`, plus three decisions left
   for the session (accent, typography, mark), under the zero-external-requests and dark-only
   AA constraints.
2. **Owner feedback (2026-08-25)** on the cards, applying to all three tabs: no ellipsis; fold the
   small-print block and the description into one clean card with a simple description (the
   detail page carries the heavy details); the whole card is the click target, with a basic
   click animation, instead of a "View details" link; "live at source" belongs on the detail
   page, not the list.
3. **A current-state audit** — the source (`frontend/app.js`, `styles.css`, `index.html`), the
   live data (52 events / 16 threats / 43 archive records), and headless-Chrome screenshots of
   every tab and a detail view at 1200px.

**One conflict, resolved in the owner's favour.** The HQ brief says *"the event cards … stay as
they are"* and *"Do not restyle the event cards."* The owner's feedback asks for exactly that
restyle. Owner instruction supersedes the brief; the cards are in scope (§2). The chrome work
the brief asked for is unchanged (§3).

---

## 1. What is actually wrong today (measured, not vibes)

The owner's read — *untidy, inconsistent, not very creative* — decomposes into these concrete
defects. Each one maps to a fix below.

### Cards

| # | Defect | Evidence |
|---|---|---|
| C1 | **Ellipsis truncation.** `.card-summary` is a 3-line `line-clamp`; the summaries it clamps are long (events: median **600 chars**, max 1,079; archive: median 562). Every event and archive card ends in "…"; threat cards don't (median 197 chars) — so truncation is also *inconsistent across tabs*. | `styles.css` `.card-summary`; screenshots |
| C2 | **The card shows the wrong text.** Cards render `event.impact.summary` / `historical.impact.summary` — by schema a *"cached snapshot of current figures"* / *"the estimate range and its uncertainty"*. That is the heavy text. The narrative `description` (*"what happened, where, where it stands"*) — the natural card teaser — is only on the detail page. Compare, for Nuristan: summary opens *"The combined confirmed death toll is at least 30: 23 killed in Parun City (125 injured, 5 missing)…"*; description opens *"Flash floods triggered by heavy rainfall struck Afghanistan's eastern Nuristan Province around 19 July 2026…"* | `app.js` `eventParts`/`historicalParts`; schema `description` fields |
| C3 | **The small-print block is a second paragraph.** Under the summary, events print `region · date · scale` — and `region` (≤200 chars) and `scale` (up to **275 chars** in live data) are free text used as prose, e.g. *"Iran, Israel and Lebanon, with strikes and shipping disruption spreading across Jordan, Saudi Arabia, the UAE, Qatar, Kuwait, Bahrain, Iraq, Oman and the Strait of Hormuz, Iran · 2026-08-17 · Interstate war since 28 February 2026 between…"* — three lines of 0.85rem text competing with the description. Then a *Figures as of … — live at source ↗* line, then a ruled footer *"N cited claims · View details →"*. | `app.js:240-249, 285-289` |
| C4 | **Card anatomy differs per tab.** Events: summary + loc line + live line + footer. Threats: summary + "Last updated" + footer. Archive: optional kicker + summary + loc + deaths line + footer. Three shapes for one component. | `app.js` per-kind adapters |
| C5 | **Badge grammar differs per tab.** Events: `verified · Flood · ongoing` (bare words, mixed case). Threats: `severity: continental · probability: very-low` (key: value). Archive: `verified · War · c. 2004 BCE` (a date as a chip). | `app.js:214-219, 232-237, 259-264` |
| C6 | **Colours are double-booked.** Green = *verified* **and** *resolved*; amber = *partial* **and** *contained* **and** *under review*; red = *disputed* **and** *ongoing*. An event card shows a green pill next to a red pill, and neither is the card's subject. 51 of 52 events and 15 of 16 threats are `verified`, so the loud green pill carries almost no information on the list — the exceptions (1 partial each) are what matter. | `styles.css` badge rules; data counts |
| C7 | **Badge row wraps unpredictably.** `space-between` puts chips right of the title when they fit and on their own row when they don't — adjacent cards look different (visible on "Large-Scale Cyberattack on Critical Infrastructure"). | screenshot, threats |
| C8 | **No click affordance beyond a text link.** The title is a link and the footer has "View details →", but the card surface is inert; hovering does nothing. | `styles.css` `.card` |
| C9 | **The map tooltip truncates too** — summary cut at 120 chars with "…". | `map.js` `showTip` |

### Chrome (the HQ brief's gaps, confirmed)

| # | Defect |
|---|---|
| H1 | No favicon (browser tab shows the default icon). |
| H2 | Header is a bare `<h1>` + a four-line tagline with four bold fragments — no mark, no wordmark, no nav, no author, no code link. A visitor from the GitHub profile can't tell whose site this is. |
| H3 | "World Pulse" appears twice in a row — active tab, then the pane `<h2>` directly beneath it (same for the other tabs). |
| H4 | Footer exists but is three paragraphs of explanation with inline badge samples; the site's strongest credibility claim — a deterministic gate decides what publishes, never the model — appears nowhere on the page. |
| H5 | `system-ui` everywhere; no type pairing, no scale — headings are just bolder body text. |
| H6 | Text OG tags exist; no `og:image`. |

### Detail page

| # | Defect |
|---|---|
| D1 | Raw gate string leaks: *"Last updated 2026-08-24 · gate: 7 verified, 0 disputed, 0 unverified -> verified (confidence: high)"* — internal notation (`->`) on a public page. |
| D2 | "Overview" prints the figures summary **then** the description — the two paragraphs repeat the same numbers back to back (see Nuristan: "at least 30 … 1,168 families … 191 families" appears in both). Backwards order too: narrative should lead, figures follow. |
| D3 | Map-jump and detail share `.card-head`; whatever the list card becomes, the detail head must match it. |

### Nothing is wrong with

Contrast (every current token clears AA on every surface: `--muted` 6.76:1 on panel, `--accent` 7.13:1, worst is `--red` 4.69:1 on `--panel-2` — still ≥4.5), the map, the tab router, the freshness/staleness line, the filter toolbars, the data. Keep all of it.

---

## 2. Target: one card, three tabs

### 2.1 Anatomy (identical for events, threats, archive)

```
┌──────────────────────────────────────────────────────────────┐
│ FLOOD · AFGHANISTAN · 19 JUL 2026 · ● ONGOING       ✓ verified│  dateline (one short line, muted, small caps)
│ Nuristan Flash Floods, Afghanistan                          → │  title (h3) — the whole card is the link
│ Flash floods triggered by heavy rainfall struck Afghanistan's │  teaser: first sentence of `description`,
│ eastern Nuristan Province around 19 July 2026.                │  complete — never clamped, never "…"
└──────────────────────────────────────────────────────────────┘
```

Three elements, in this order, and nothing else. (As shipped, dates in the dateline are ISO —
`2026-07-19` — matching the freshness line and the updates timeline; the mock's "19 Jul 2026" was
not adopted. A `country` written as prose is reduced to its bare place and dropped past 40 chars.)

1. **Dateline** — the scannable facts, as one short muted line *above* the title (an eyebrow, not
   a second paragraph). Per tab, built only from **short structured fields** — never `region`,
   `scale`, or the summary:
   - Pulse: `<category> · <country> · <occurrence_date> · ● <status>`
   - Threats: `Severity <severity> · Probability <estimate>`
   - Archive: `<type> · <date_display> · <country>`
   The trust mark sits at the right end of the same line (see 2.3). The archive's `CHIP_MAX_CHARS`
   kicker special case goes away — the dateline simply wraps (1 of 43 records is over 40 chars).
2. **Title** — `rec.name`, the card's accessible name and its link.
3. **Teaser** — the **first sentence of `description`**, in full. Measured on live data: median
   250 chars (events) / 169 (threats) / 219 (archive), longest 571. Two to four lines at 74ch,
   no truncation. See 2.2 for how it is derived and why not a new field.

Removed from the card (all of it lives on the detail page already): the figures summary, the
`region · date · scale` line, *Figures as of / live at source*, the deaths-range line, "Last
updated", the "N cited claims · View details →" footer, and the three-chip badge row.

### 2.2 The teaser — derive it, don't add a field (for now)

**Rule:** `teaserOf(rec)` = the first sentence of `description`; sentence end = `.`, `!` or `?`
followed by whitespace and an uppercase letter, an opening quote or a bracket, **except** after a
known abbreviation (`c.`, `St.`, `No.`, `vs.`, `U.S.`, `U.K.`, `Mt.`, `Dr.`, a single capital
initial, a magnitude like `M7.4`). If no boundary is found, the whole description is the teaser.
Never truncate what the rule returns.

**Why derived, not a schema field:** it keeps the pass frontend-only (`data/`, `data/schema/`,
`pipeline/`, the three refresh commands and their tests are untouched — the HQ brief's
constraint, and the trust gate's scope stays exactly as documented), and it needs no backfill of
111 records. The descriptions are already *current-state prose rewritten in place on every
refresh* (schema + `tests/test_prose.py`), so the first sentence is always current.

**Soft steering, not enforcement:** add one line to each `/refresh-*` command — *"the first
sentence of `description` is the card's teaser: one plain sentence, ideally ≤ 200 characters"*.
That is a prompt edit, not a gate change, and the data converges on its own through the daily
rewrite. Escalation path if derived teasers read badly in practice: promote to an explicit
`teaser` field (schema + `curate._normalize` + `audit` + refresh commands + one-off backfill) —
recorded as a follow-up in §7, not done now.

### 2.3 Trust and status signals, untangled (fixes C5–C7)

- **Trust** is the *only* thing rendered as a chip, and it is quiet when it is the norm and
  loud when it is the exception:
  - `verified` → `✓ verified` as small muted-green **text** (no fill).
  - `partial`, `disputed`, `unverified`, `under review` → **filled** amber/red pill, exactly
    today's colours. These are rare (2 of 111 records) and should be the only colour block on
    a card.
- **Event status** moves into the dateline as text with a 6px dot: `● ongoing` (red),
  `● contained` (amber), `● resolved` (grey — not green, so green stays trust-only).
- **Category / severity / probability / date** are plain dateline text. No chips.
- Map markers keep their impact colours (grey → blue → amber → red); no card element reuses
  that scale for a different meaning.

### 2.4 Whole-card click + animation (fixes C8)

- **Stretched-link pattern**, not `<a>` around the card: `.card { position: relative }` and
  `.card-title-link::after { content: ""; position: absolute; inset: 0 }`. The card keeps its
  `<article id="card-<id>">` (the map's `jumpToCard` target and `card-flash` still work), the
  accessible name stays the title, keyboard focus lands on one link, and there are no nested
  interactive elements left inside once *live at source* moves out.
- **Motion:** `transition: transform 160ms ease-out, border-color 160ms, box-shadow 160ms`;
  hover → `translateY(-2px)`, border to accent at ~50%, a soft shadow; `:active` →
  `translateY(0)`; a faint `→` at the card's top-right that brightens and nudges 3px on hover.
  Focus: `.card:has(.card-title-link:focus-visible)` draws the same ring the site uses
  everywhere. `@media (prefers-reduced-motion: reduce)` keeps the colour change, drops the
  transform (mirrors the existing `card-flash` handling).
- `cursor: pointer` on the whole card.

### 2.5 Map tooltip (fixes C9)

`showTip` renders **name + dateline** instead of a 120-char summary slice. No ellipsis anywhere
on the site.

---

## 3. Chrome: the identity floor (the HQ brief, unchanged in scope)

- **Masthead** — small mark + wordmark *Global Observatory* as the `h1`, one-line tagline
  (*"A fact-based observatory of the world — an aggregation of published figures, not a
  forecast."*), and a right-aligned nav with two links: **Code** → the repo,
  **Guillermo Arria-Devoe** → the profile. Same pattern the swing-lab dashboard shipped
  2026-08-24 (decorative SVG `aria-hidden="true" focusable="false"`, wordmark carries the name).
- **Tabs** stay the section nav directly under the masthead. Fix H3 by making the pane's
  `pane-sub` + freshness line the pane head and dropping the visible duplicate title (keep an
  `h2` for the outline; visually it *is* the active tab).
- **Favicon** — the same mark as an inline SVG data URI in `<link rel="icon">` (swing-lab's
  method; zero external requests preserved).
- **Footer** — three short lines: the trust-gate sentence (*"What publishes here is decided by
  a deterministic gate — every headline figure must resolve to an allowlisted authoritative
  source; the curator never gets the final say"*), a one-line badge legend (the backlog's
  open "trust-badge legend" item), and *Code · Built and curated by Guillermo Arria-Devoe*.
- **`og:image`** — optional 1200×630 PNG of mark + wordmark on `--bg`; do it only if it takes
  under 20 minutes, else leave the text tags.
- **Type scale** — a real scale (h1 2.25rem / pane 1.5rem / card title 1.125rem / body 1rem /
  dateline 0.75rem) instead of ad-hoc sizes, and a display face per decision D2.

---

## 4. Detail page (the "heavy details" home)

- Head reuses the new card anatomy (dateline · title · trust mark) so list → detail reads as a
  zoom, not a different site.
- **Facts block** right under the head, in this order: full location line (`region`, `country`
  — the long free text belongs *here*), `scale`, *Figures as of <date> · live at source ↗*
  (the link's new and only home), *Last updated*.
- **D1:** render `verification.status` + `confidence` in words (*Verified · confidence high ·
  7 of 7 claims resolve to allowlisted sources*); the raw `notes` string goes in a `title`
  attribute, not on the page.
- **D2:** *Overview* = `description` (narrative). *Key figures* = the numeric lines **plus** the
  figures summary (`impact.summary` / `assessment.summary`) as its paragraph — figures live
  with figures, and the two texts are no longer printed back to back.
- *Updates* and *Citations* unchanged.

---

## 5. Decisions for the owner — all seven taken as recommended, 2026-08-25

| # | Decision | Recommendation | Why |
|---|---|---|---|
| **D1** | Accent | **Keep `#6ea8fe`.** | Already 7.8:1 on `--bg` / 7.1:1 on `--panel`; the identity gain comes from the mark and type, not from churning a colour that passes AA on every surface. Per-project accents remain the portfolio principle — if changed, recompute every ratio (script in §8). |
| **D2** | Typography | **One self-hosted display face for wordmark + headings + card titles; body stays `system-ui`.** Candidate: Newsreader (OFL), one weight (600), latin subset woff2 (~20–30 KB), under `frontend/assets/fonts/`. | Keeps the zero-external-requests property (a `<link>` to any font host breaks it). Newsreader is VAS's display face — that is the "three sites, one person" signal the Q lane wants, and Q3 extracts the shared type foundation from what GO ships. Budget is a non-issue: the basemap alone is 736 KB. Alternative: `system-ui` only (zero cost, zero identity). |
| **D3** | The mark | **Globe with a pulse line** — a circle, one meridian, a single ECG-style spike across the equator; ≤ 30 lines of SVG, single-colour on `--bg`, used identically in masthead and favicon. | Reads at 16px; says "observatory" + "pulse" without text. Draft two variants in-session, pick one. |
| **D4** | Dateline on the card | **Yes, one short line above the title** (§2.1). | Pure "title + teaser" is the strictest reading of the feedback, but 52 events are unscannable without *where/when*. The dateline is metadata-sized (0.75rem, muted) and sits *above* the title, so it never competes with the description. Option: drop it and rely on the teaser sentence carrying place and date. |
| **D5** | Trust/status treatment | **Quiet-verified, loud-exception; status as a dot in the dateline** (§2.3). | 96% of records are `verified`; a filled green pill on every card is noise. The one `partial` record becomes the only coloured block on its tab — which is what the trust model wants seen. |
| **D6** | Archive deaths range on the card | **No** — detail page only. | "Simple description" rule. It is the archive's one number, so this is the easiest decision to reverse: `Estimated deaths: 75K–100K` could join the dateline. |
| **D7** | Teaser source | **Derived first sentence of `description`** (§2.2). | Frontend-only; converges via daily rewrite. Promote to a schema field only if derived teasers read badly after a week of refreshes. |

---

## 6. Phases

Each phase is one PR, merged only after §8 passes in full. Order chosen by visible impact per
hour; Phase 2 is independent of Phase 1 and can be swapped ahead if the owner wants the identity
first.

### Phase 1 — Card system (owner feedback; the biggest visible change)

Files: `frontend/app.js`, `frontend/styles.css`, `frontend/map.js` (tooltip only).

1. Add `teaserOf(rec)` (§2.2) and `datelineOf(rec, kind)` (§2.1) next to the existing per-kind
   adapters; the adapters return `{ dateline, trust, teaser }` and nothing else.
2. Rewrite `cardNode`: `article.card#card-<id]` → `.card-dateline` (+ `.card-trust` at right)
   → `h3 > a.card-title-link` → `p.card-teaser`. Delete `.card-summary` clamp, `.card-loc`,
   `.card-live`, `.card-meta`, `.card-kicker`, `.card-foot`, `CHIP_MAX_CHARS`, the
   `badge-sev/prob/scale/cat/ongoing/contained/resolved` rules.
3. Stretched link + motion + focus + reduced-motion (§2.4); keep `.card-flash` working.
4. Trust mark: `verified` as text, others as today's pills (§2.3).
5. `map.js` `showTip`: name + dateline.
6. Add the one-line teaser steer to the three `/refresh-*` commands (`.claude/commands/`);
   prompt text only — no gate, no schema.

Acceptance: no `…` anywhere on any tab; every card on all three tabs has the same three
elements; clicking anywhere on a card opens its detail route; Tab key reaches each card once;
map marker → card flash still works; 320px shows no horizontal scroll.

### Phase 2 — Identity chrome (the HQ brief)

Files: `frontend/index.html`, `frontend/styles.css`, `frontend/assets/fonts/*` (if D2 = yes).

1. Tokens: add `--font-display`, the type scale, `--accent-soft` (accent at ~50% for hover
   borders), `--ok-text` (muted green for `✓ verified`, contrast-checked).
2. Masthead (mark + wordmark + tagline + nav), favicon data URI, footer (§3).
3. Pane heads lose the duplicate title (H3).
4. Optional `og:image` (§3).

Acceptance: every new text colour ≥ 4.5:1 on its surface (script in §8); `curl` of the built
page shows no request to any host but the page's own; masthead + nav wrap cleanly at 320px.

### Phase 3 — Detail page + tidy (§4)

Files: `frontend/app.js` (`detailNode`, `detailMeta`, `detailFigures`), `frontend/styles.css`.

Acceptance: no `->` or `gate:` text on any detail page; *live at source* present on every event
detail; Overview shows `description` once; Key figures shows the figures summary once.

### Phase 4 — Docs

`README.md` frontend paragraph (card anatomy, teaser rule, the font asset if any),
`docs/ARCHITECTURE.md` §6 (the derived-teaser rule and the stretched-link pattern belong next to
the "no external requests" sentence), `BACKLOG.md` (close the identity item, record D1–D7 as
taken, add §7 follow-ups).

---

## 7. Follow-ups (recorded, not scheduled)

- **Explicit `teaser` field** if derived teasers read badly (D7 escalation) — touches schema,
  `curate._normalize`, `audit`, three refresh commands, tests, one-off backfill of 111 records.
- **`og:image`** if skipped in Phase 2.
- **Body face** (Atkinson Hyperlegible, self-hosted) if D2's display face lands well and the
  portfolio spec (HQ Q3) asks for a shared body face — GO's choice is one of the three inputs
  to that spec, so ship first, standardise after.
- **Search + pulse category filter** (existing "Richer UI" item) — the new dateline makes
  category visible, which may make a filter feel missing.
- The `region` and `scale` fields are being written as prose (up to 275 chars). Not a frontend
  bug once they leave the card, but worth a cap in the refresh prompt so the detail page's
  facts block stays a facts block.

---

## 8. Constraints and the verification recipe (run all of it before each merge)

**Constraints carried from the brief and the repo:**
- Zero external requests — every byte served from `frontend/`; fonts self-hosted or none.
- Dark-only; ≥ 4.5:1 for all small text — computed, never eyeballed.
- No page-level horizontal scroll at 320px (`styles.css` documents why `overflow-x: clip`).
- Nothing under `data/`, `data/schema/`, `pipeline/` changes in this pass.
- Card `id="card-<id>"` and the two-method `GOMap` API are contracts with `map.js`.
- Code reaches `main` by human merge (`publish.yml` scopes auto-merge to data); a push to
  `main` touching `frontend/**` **is** the deploy (`pages.yml`). Standing authorisation: merge
  Claude-authored PRs after full local validation, merge commits not squash.

**Recipe** (system Python is 3.10; the repo needs ≥ 3.11 — use a uv venv in the scratchpad):

```sh
uv venv "$S/venv" --python 3.12 && uv pip install --python "$S/venv/bin/python" -e ".[dev]"
"$S/venv/bin/ruff" check . && "$S/venv/bin/python" -m pytest -q
"$S/venv/bin/python" scripts/validate_data.py && "$S/venv/bin/python" scripts/build_frontend.py
git diff --exit-code frontend/data/     # aggregates must not change in a frontend pass

# Render every route at desktop width. Two gotchas, both paid for on 2026-08-25:
#  - a reused --user-data-dir serves app.js/styles.css from Chrome's HTTP cache and
#    silently renders the OLD code — use a fresh profile dir per run (rm it after);
#  - a 2600px-tall window sometimes captures a blank band where the header is; that is
#    a capture artifact (re-render at 1200x900 to confirm), not a layout bug.
(cd frontend && python3 -m http.server 8765 --bind 127.0.0.1 &) ; sleep 1
for r in pulse threats history "pulse/$(python3 -c "import json;print(json.load(open('frontend/data/events.json'))['published'][0]['id'])")"; do
  google-chrome --headless=new --no-sandbox --disable-gpu --hide-scrollbars \
    --user-data-dir="$S/chrome-$$" --disk-cache-size=1 --virtual-time-budget=6000 \
    --window-size=1200,2600 --screenshot="$S/$(echo $r | tr / _).png" "http://127.0.0.1:8765/#$r"
done
# 320px: headless enforces a ~500px minimum window, so wrap the site in a 320px iframe:
echo '<iframe src="http://127.0.0.1:8765/#threats" style="width:320px;height:1900px;border:0"></iframe>' > "$S/narrow.html"
google-chrome --headless=new --no-sandbox --disable-gpu --hide-scrollbars --user-data-dir="$S/chrome-n-$$" \
  --virtual-time-budget=6000 --window-size=520,1900 --screenshot="$S/narrow.png" "file://$S/narrow.html"

# No ellipsis, no leaked gate string, no external URL in the shipped page:
grep -n '…' frontend/app.js frontend/map.js ; grep -n 'gate:' frontend/app.js
grep -nE 'https?://' frontend/index.html frontend/styles.css | grep -vE 'github.com/guillearria|guillearria.github.io|w3.org/2000/svg'
```

Contrast check (stdlib only) — run for every new `(text, surface)` pair:

```python
def lum(h):
    h=h.lstrip('#'); r,g,b=[int(h[i:i+2],16)/255 for i in (0,2,4)]
    f=lambda c: c/12.92 if c<=0.03928 else ((c+0.055)/1.055)**2.4
    return 0.2126*f(r)+0.7152*f(g)+0.0722*f(b)
def ratio(a,b):
    x,y=lum(a),lum(b); return (max(x,y)+0.05)/(min(x,y)+0.05)   # need >= 4.5 for small text
```

---

## 9. Round 2 — owner feedback on the shipped pass (2026-08-26)

Seven points, all frontend; shipped as one PR the same day.

1. **Tagline → About.** The masthead is now mark + wordmark + nav only. A fourth tab, **About**
   (`#about`, static, no data, no detail routes — `parseRoute` drops any id under it), carries
   what the site is, where the figures come from, and who makes it — in reader language: no
   "allowlist", "gate" or "quarantine" on the page.
2. **Dateline separators** are pipes with air (`|`, 0.55em margins, 45% opacity) at 0.78rem /
   0.06em tracking, instead of cramped middle dots.
3. **Status sits on the right** with the signal group (● ongoing / contained / resolved), beside
   the arrow — the left side is facts only (category | country | date).
4. **Verified is unlabelled.** A card shows a pill only when the record is the exception
   (`partial`, `under review`, …); the citations list shows a pill only on a claim that is not
   verified. Verification is the baseline of the whole site, so labelling it on 594 claims was
   noise. The detail page keeps the verdict, reworded for readers: *"3 of 4 sources confirmed ·
   confidence medium · 1 cited page could not be re-opened (see citations)"*.
5. **Footer** is swing-lab's form exactly: *Project code on GitHub · Built by Guillermo
   Arria-Devoe*. The trust-gate sentence and the badge legend moved to About.
6. **The "partial vs. verified system" is kept in the pipeline, not deprecated** — it is what
   makes "thoroughly verified" a checked property rather than a claim — but it no longer
   appears on the list surfaces. Owner's read stands: the gate context is for us, the reader
   sees sources and dates.
7. **What "partial" actually is, measured:** 594 claims across the site, **5 unverified** — and
   every one cites an *allowlisted* domain (ReliefWeb ×1, UNHCR ×1, Britannica ×3). The gate
   never downgraded them; the curating session could not open those pages (UNHCR and Britannica
   block automated fetchers — the BACKLOG has recorded this for UNHCR since August) and
   correctly refused to call them confirmed. Not a system defect: an operational follow-up —
   five URLs to confirm by hand, then flip through `curate.write` — recorded in the BACKLOG.
   *Round 3 (2026-08-26): the UNHCR claim was confirmed in a real browser (the total lives in
   the chart's hidden data table, not the prose) and flipped — `2fd54b4`. The four Britannica /
   ReliefWeb claims remain: both domains 403 every fetcher and are outside the browser
   extension's site permissions.* *Later that day, with the extension allowed on all sites:
   Aleppo 1138 and Yangtze 1931 confirmed verbatim and flipped (`b34a7dc`); the Thirty Years'
   War claim turned out to cite a page that does not state its figures — a re-sourcing job for
   `/refresh-history`, recorded in the BACKLOG; ReliefWeb remains refused by the extension.*
   Round 3 also moved the card arrow onto the dateline row,
   put the About tab in line, rebuilt About as three panels, and dropped the redundant
   attribution (PR #21).
