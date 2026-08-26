"use strict";

// --- Router (hash-routed tabs + record detail views) -------------------------
// #pulse / #threats / #history are the list tabs; #<tab>/<record-id> is that
// record's detail view. All shareable URLs; back button walks the history.
const TABS = ["pulse", "threats", "history"];

const TAB_KINDS = { pulse: "event", threats: "threat", history: "historical" };
const KIND_TABS = { event: "pulse", threat: "threats", historical: "history" };

const PANE_TITLES = {
  pulse: "World Pulse", threats: "Existential Threats", history: "Historical Archive",
};

const SITE_TITLE = document.title;

function parseRoute() {
  const [tab, id] = location.hash.replace(/^#/, "").split("/");
  // Unknown tab -> default list; extra segments beyond the id are ignored.
  return { tab: TABS.includes(tab) ? tab : "pulse", id: id || null };
}

function detailHref(tab, id) {
  return `#${tab}/${id}`;
}

function showView(route) {
  const detailPane = document.getElementById("detail-pane");
  // List panes stay mounted even behind a detail view: the map's click-to-card
  // targets and the toolbars' filter state live in them.
  for (const tab of TABS) {
    const pane = document.getElementById(`${tab}-pane`);
    if (pane) pane.hidden = route.id !== null || tab !== route.tab;
  }
  if (detailPane) detailPane.hidden = route.id === null;
  for (const link of document.querySelectorAll(".tabs a")) {
    const active = link.dataset.tab === route.tab;
    link.classList.toggle("active", active);
    if (active) link.setAttribute("aria-current", "page");
    else link.removeAttribute("aria-current");
  }
  if (route.id !== null) {
    renderDetail(route);
    window.scrollTo(0, 0);
    return;
  }
  document.title = SITE_TITLE;
  // A map laid out while its pane was hidden has zero size — re-measure on show.
  // Runs on every return from a detail view too; invalidate is cheap and bails
  // itself at zero width.
  if (route.tab === "pulse" && window.GOMap) GOMap.invalidate();
}

// --- Threat categories (existential threats pane) --------------------------
// Fixed display order; any unknown category is appended after these.
const CATEGORY_ORDER = [
  "cosmic", "geological", "nuclear", "biological",
  "climate", "technological", "resource", "societal",
];

const CATEGORY_LABELS = {
  cosmic: "Cosmic", geological: "Geological", nuclear: "Nuclear",
  biological: "Biological", climate: "Climate", technological: "Technological",
  resource: "Resource", societal: "Societal",
};

// --- Event types (World Pulse pane) ----------------------------------------
const EVENT_TYPE_LABELS = {
  earthquake: "Earthquake", storm: "Storm", flood: "Flood", wildfire: "Wildfire",
  volcanic: "Volcanic", drought: "Drought", outbreak: "Outbreak", conflict: "Conflict",
  humanitarian: "Humanitarian crisis", economic: "Economic crisis", industrial: "Industrial",
  other: "Event",
};

// --- Historical eras and types (historical archive pane) --------------------
const ERA_ORDER = ["ancient", "classical", "medieval", "early-modern", "modern", "contemporary"];

const ERA_LABELS = {
  ancient: "Ancient", classical: "Classical", medieval: "Medieval",
  "early-modern": "Early Modern", modern: "Modern", contemporary: "Contemporary",
};

const HISTORICAL_TYPE_LABELS = {
  pandemic: "Pandemic", war: "War", famine: "Famine", "natural-disaster": "Natural disaster",
  "societal-collapse": "Societal collapse", genocide: "Genocide", economic: "Economic crisis",
  other: "Event",
};

// Canonical severity order (threat.schema.json enum) for the threats filter.
const SEVERITY_ORDER = ["regional", "continental", "civilizational", "extinction"];

// --- Sort/filter toolbars (threats + history panes) -------------------------
// In-memory view state; resets on reload by design. World Pulse has no controls.
const viewState = {
  history: { sort: "oldest", category: "all" },
  threats: { category: "all", severity: "all" },
};

// Latest per-pane re-render callback, registered by loadPane, so a toolbar
// change re-renders from the already-loaded data without refetching.
const paneRerender = {};

// Latest data per pane (same mount ids as the route tab names), so detail
// routes render from the already-loaded aggregate without their own fetch.
const paneData = {};

function el(tag, attrs, children) {
  const node = document.createElement(tag);
  if (attrs) {
    for (const [k, v] of Object.entries(attrs)) {
      if (k === "class") node.className = v;
      else if (k === "text") node.textContent = v;
      else node.setAttribute(k, v);
    }
  }
  for (const child of children || []) {
    if (child) node.appendChild(child);
  }
  return node;
}

function badge(text, cls) {
  return el("span", { class: `badge ${cls}`, text });
}

// --- Card text: the teaser --------------------------------------------------
// A card is three things: a dateline of short structured facts, the title, and
// a teaser. The teaser is the first sentence of `description`, shown complete —
// never clamped, never an ellipsis; the detail view carries everything else.
// A sentence ends at . ! or ? followed by whitespace and a capital, digit,
// quote or bracket, unless the period closes a known abbreviation or an initial
// ("c. 1600 BCE", "No. 3", "U.S.", "St. Louis"). No boundary -> the whole text.
const ABBREVIATIONS =
  /\b(?:c|ca|St|No|Nos|vs|Mt|Dr|Mr|Mrs|Ms|Prof|Gen|Col|Lt|Sgt|approx|est|fig|vol|pp|U\.S|U\.K|U\.N|e\.g|i\.e|Jr|Sr|Inc|Ltd|Co|[A-Z])$/;

function firstSentence(text) {
  const re = /[.!?]["'”’)\]]*(?=\s+["'“‘(\[]?[A-Z0-9])/g;
  let m;
  while ((m = re.exec(text)) !== null) {
    if (text[m.index] === "." && ABBREVIATIONS.test(text.slice(0, m.index))) continue;
    return text.slice(0, m.index + m[0].length);
  }
  return text;
}

function teaserOf(rec, fallback) {
  const text = (rec.description || fallback || "").trim();
  return text ? firstSentence(text) : "";
}

function dateOnly(iso) {
  return (iso || "").slice(0, 10);
}

// Days between an ISO timestamp and now; NaN (falsy checks below) if unparseable.
function daysSince(iso) {
  if (!iso) return NaN;
  const then = Date.parse(iso);
  if (Number.isNaN(then)) return NaN;
  return (Date.now() - then) / 86400000;
}

function linkOut(url, text) {
  return el("a", { href: url, target: "_blank", rel: "noopener noreferrer", text });
}

function compositeOf(rec) {
  return (rec.sort_keys && typeof rec.sort_keys.composite === "number")
    ? rec.sort_keys.composite : 0;
}

function chronologyOf(rec) {
  return (rec.sort_keys && typeof rec.sort_keys.chronology_rank === "number")
    ? rec.sort_keys.chronology_rank : 0;
}

function impactOf(rec) {
  return (rec.sort_keys && typeof rec.sort_keys.impact_rank === "number")
    ? rec.sort_keys.impact_rank : 0;
}

// The freshness of an event's cached figures is the claims' retrieved_date, not the
// record's last_updated (which is re-stamped on every pipeline run, even ones that
// don't touch the figures) — see event.schema.json's documented invariant.
function latestRetrievedDate(claims) {
  const dates = (claims || []).map((c) => c.retrieved_date).filter(Boolean);
  return dates.length ? dates.reduce((a, b) => (a > b ? a : b)) : "";
}

const compactNumber = new Intl.NumberFormat("en", {
  notation: "compact", maximumFractionDigits: 1,
});

// "Estimated deaths: 75M–200M" from a deaths_low/deaths_high range; historical tolls
// are ranges, not counts, so both bounds are shown when they differ.
function formatDeathsRange(impact) {
  const lo = impact.deaths_low, hi = impact.deaths_high;
  const loNum = typeof lo === "number", hiNum = typeof hi === "number";
  if (!loNum && !hiNum) return "";
  if (loNum && hiNum && lo !== hi) {
    return `Estimated deaths: ${compactNumber.format(lo)}–${compactNumber.format(hi)}`;
  }
  return `Estimated deaths: ~${compactNumber.format(loNum ? lo : hi)}`;
}

function claimNode(claim) {
  const src = el("div", { class: "claim-src" });
  const status = claim.verification_status || "unverified";
  src.appendChild(badge(status, `badge-${status}`));
  if (claim.source_url) {
    src.appendChild(linkOut(claim.source_url, claim.source_name || claim.source_url));
  } else if (claim.source_name) {
    src.appendChild(el("span", { text: claim.source_name }));
  }
  if (claim.retrieved_date) {
    src.appendChild(el("span", { text: `retrieved ${claim.retrieved_date}` }));
  }
  return el("div", { class: "claim" }, [
    el("p", { class: "claim-text", text: claim.text || "" }),
    src,
  ]);
}

// --- Per-kind adapters: dateline facts + status + teaser -------------------
// Each returns { facts: string[], status?: string, teaser }. Facts are short
// structured fields only — never region, scale or a summary: those are prose
// and belong on the detail view. The trust mark is added by trustNode().

// `location.country` is sometimes written as prose ("Roman Empire (Mediterranean,
// Europe, ...)", "Turkey (Ottoman Empire); modern Armenia, Syria"). The dateline
// takes the bare place — the first clause, minus a trailing parenthetical — and
// drops it altogether past this length; the detail view shows the full text.
const PLACE_MAX_CHARS = 40;

function placeOf(location) {
  const raw = ((location || {}).country || "").split(";")[0];
  const place = raw.replace(/\s*\([^()]*\)\s*$/, "").trim();
  return place.length <= PLACE_MAX_CHARS ? place : "";
}

function threatParts(rec) {
  const a = rec.assessment || {};
  const facts = [
    a.severity ? `Severity ${a.severity}` : "",
    (a.probability || {}).estimate ? `Probability ${a.probability.estimate}` : "",
  ];
  return { facts, teaser: teaserOf(rec, a.summary) };
}

function eventParts(rec) {
  const ev = rec.event || {};
  const facts = [
    EVENT_TYPE_LABELS[rec.category] || rec.category || "Event",
    placeOf(ev.location),
    dateOnly(ev.occurrence_date),
  ];
  return { facts, status: ev.status || "ongoing", teaser: teaserOf(rec, (ev.impact || {}).summary) };
}

function historicalParts(rec) {
  const hist = rec.historical || {};
  const facts = [
    HISTORICAL_TYPE_LABELS[rec.category] || rec.category || "Event",
    hist.date_display || "",
    placeOf(hist.location),
  ];
  return { facts, teaser: teaserOf(rec, (hist.impact || {}).summary) };
}

function partsFor(rec, kind) {
  return kind === "event" ? eventParts(rec)
    : kind === "historical" ? historicalParts(rec)
    : threatParts(rec);
}

// The kind's figures snapshot (impact / assessment summary): detail view only.
function kindSummary(rec, kind) {
  if (kind === "event") return ((rec.event || {}).impact || {}).summary || "";
  if (kind === "historical") return ((rec.historical || {}).impact || {}).summary || "";
  return (rec.assessment || {}).summary || "";
}

// Plain-text dateline — also the map tooltip's second line (see main()).
function datelineText(rec, kind) {
  const parts = partsFor(rec, kind);
  return [...parts.facts, parts.status].filter(Boolean).join(" · ");
}

// Trust is the only thing rendered as a chip, and only loudly when it is the
// exception: `verified` (the norm) is quiet text; partial / disputed /
// unverified / under review keep the filled pill so they are the one block of
// colour on a list.
function trustNode(rec, review) {
  const status = review ? "review" : ((rec.verification || {}).status || "unverified");
  if (status === "verified") return el("span", { class: "card-trust trust-ok", text: "✓ verified" });
  return el("span", {
    class: `card-trust badge badge-${status}`,
    text: status === "review" ? "under review" : status,
  });
}

function datelineNode(rec, parts, review) {
  const facts = el("span", { class: "card-facts" });
  const segments = parts.facts.filter(Boolean);
  segments.forEach((f, i) => {
    if (i) facts.appendChild(el("span", { class: "card-sep", text: " · " }));
    facts.appendChild(el("span", { text: f }));
  });
  if (parts.status) {
    if (segments.length) facts.appendChild(el("span", { class: "card-sep", text: " · " }));
    facts.appendChild(el("span", { class: `card-status status-${parts.status}`, text: parts.status }));
  }
  return el("p", { class: "card-dateline" }, [facts, trustNode(rec, review)]);
}

// The whole card is the link: the title anchor's ::after stretches over the
// article (styles.css), so the accessible name stays the title, Tab lands on
// one link per card, and the article id remains the map's jump target.
function cardNode(rec, { review, kind }) {
  const parts = partsFor(rec, kind);
  const href = detailHref(KIND_TABS[kind], rec.id);
  return el("article", { class: "card", id: `card-${rec.id}` }, [
    el("span", { class: "card-arrow", "aria-hidden": "true", text: "→" }),
    datelineNode(rec, parts, review),
    el("h3", { class: "card-title" }, [el("a", { href, class: "card-title-link", text: rec.name || rec.id })]),
    parts.teaser ? el("p", { class: "card-teaser", text: parts.teaser }) : null,
  ]);
}

// --- Detail view (#<tab>/<record-id>): one record as a full page ------------
function findRecord(data, id) {
  for (const rec of data.published || []) if (rec.id === id) return { rec, review: false };
  for (const rec of data.under_review || []) if (rec.id === id) return { rec, review: true };
  return null;
}

function renderDetail(route) {
  const mount = document.getElementById("detail");
  if (!mount) return;
  const data = paneData[route.tab];
  if (!data) {
    // Cold deep link: the pane's aggregate hasn't arrived yet — loadPane's
    // render re-invokes renderDetail once it has data (cached or fetched).
    mount.replaceChildren(el("p", { class: "loading", text: "Loading…" }));
    return;
  }
  const found = findRecord(data, route.id);
  if (!found) {
    document.title = SITE_TITLE;
    mount.replaceChildren(
      el("p", { class: "error", text: "No record with this id — it may have been renamed or removed." }),
      el("p", { class: "detail-back" }, [
        el("a", { href: `#${route.tab}`, text: `← Back to ${PANE_TITLES[route.tab]}` }),
      ]),
    );
    return;
  }
  document.title = `${found.rec.name || route.id} — ${SITE_TITLE}`;
  mount.replaceChildren(detailNode(found.rec, { kind: TAB_KINDS[route.tab], review: found.review }));
}

// Meta lines for the detail head; unlike the card adapters this includes the
// verification verdict (the gate's notes string) and, for events, the
// last-updated stamp next to it.
function detailMeta(rec, kind) {
  const v = rec.verification || {};
  const verLine = [
    v.notes || (v.status ? `verification: ${v.status}` : ""),
    v.confidence ? `(confidence: ${v.confidence})` : "",
  ].filter(Boolean).join(" ");
  const out = [];
  if (kind === "event") {
    const ev = rec.event || {};
    const loc = ev.location || {};
    const where = [loc.region, loc.country].filter(Boolean).join(", ");
    const locLine = [where, dateOnly(ev.occurrence_date), ev.scale].filter(Boolean).join(" · ");
    if (locLine) out.push(el("p", { class: "card-loc", text: locLine }));
    if (ev.live_source_url) {
      const asOf = dateOnly(latestRetrievedDate(rec.claims)) || dateOnly(rec.last_updated);
      out.push(el("p", { class: "card-live" }, [
        el("span", { text: `Figures as of ${asOf} — ` }),
        linkOut(ev.live_source_url, "live at source ↗"),
      ]));
    }
    out.push(el("p", {
      class: "card-meta",
      text: `Last updated ${dateOnly(rec.last_updated)}${verLine ? ` · ${verLine}` : ""}`,
    }));
  } else if (kind === "threat") {
    out.push(el("p", { class: "card-meta", text: `Last updated ${dateOnly(rec.last_updated)}` }));
    if (verLine) out.push(el("p", { class: "card-meta", text: verLine }));
  } else {
    const hist = rec.historical || {};
    const loc = hist.location || {};
    const where = [loc.region, loc.country].filter(Boolean).join(", ");
    if (where) out.push(el("p", { class: "card-loc", text: where }));
    out.push(el("p", {
      class: "card-meta",
      text: `Last updated ${dateOnly(rec.last_updated)}${verLine ? ` · ${verLine}` : ""}`,
    }));
  }
  return out;
}

function figureLine(label, value) {
  return el("p", { class: "figure", text: `${label}: ${value}` });
}

// Key-figure lines per kind; skipped entirely when a record has none.
function detailFigures(rec, kind) {
  const out = [];
  if (kind === "event") {
    const impact = (rec.event || {}).impact || {};
    if (typeof impact.deaths === "number") out.push(figureLine("Deaths", compactNumber.format(impact.deaths)));
    if (typeof impact.displaced === "number") out.push(figureLine("Displaced", compactNumber.format(impact.displaced)));
  } else if (kind === "threat") {
    const a = rec.assessment || {};
    const p = a.probability || {};
    if (a.severity) out.push(figureLine("Severity", a.severity));
    if (p.estimate) {
      let text = p.estimate;
      if (p.window) text += ` (window: ${p.window})`;
      if (typeof p.numeric_annual === "number") text += ` · annual ≈ ${p.numeric_annual}`;
      out.push(figureLine("Probability", text));
    }
    if (a.timeframe) out.push(figureLine("Timeframe", a.timeframe));
    if ((rec.verification || {}).confidence) out.push(figureLine("Confidence", rec.verification.confidence));
  } else {
    const hist = rec.historical || {};
    const deaths = formatDeathsRange(hist.impact || {});
    if (deaths) out.push(el("p", { class: "figure", text: deaths }));
    if (hist.date_display) out.push(figureLine("Date", hist.date_display));
  }
  return out;
}

function detailSection(title, children) {
  return el("section", { class: "detail-section" }, [
    el("h3", { text: title }),
    ...children,
  ]);
}

function detailNode(rec, { kind, review }) {
  const tab = KIND_TABS[kind];
  const parts = partsFor(rec, kind);

  const children = [
    el("p", { class: "detail-back" }, [
      el("a", { href: `#${tab}`, text: `← Back to ${PANE_TITLES[tab]}` }),
    ]),
  ];
  if (review) {
    children.push(el("div", {
      class: "review-banner",
      text: "This record failed automated verification — no authoritative source has been " +
            "confirmed for its headline claims. It is shown for transparency and must not " +
            "be read as established fact.",
    }));
  }
  // Same head as the list card (dateline, then the title), so list -> detail
  // reads as a zoom rather than a different page.
  children.push(datelineNode(rec, parts, review));
  children.push(el("h2", { class: "detail-title", text: rec.name || rec.id }));
  children.push(el("div", { class: "detail-meta" }, detailMeta(rec, kind)));

  const figures = detailFigures(rec, kind);
  if (figures.length) children.push(detailSection("Key figures", figures));

  // The kind summary first, then the description — they are separate editorial
  // texts (snapshot vs. narrative); the second is skipped when identical.
  const summary = kindSummary(rec, kind);
  const description = rec.description || "";
  const prose = [];
  if (summary) prose.push(el("p", { class: "detail-prose", text: summary }));
  if (description && description !== summary) {
    prose.push(el("p", { class: "detail-prose", text: description }));
  }
  if (prose.length) children.push(detailSection("Overview", prose));

  if (kind === "event" && Array.isArray(rec.updates) && rec.updates.length) {
    children.push(detailSection("Updates", rec.updates.map((u) => el("div", { class: "update" }, [
      el("span", { class: "update-date", text: u.date || "" }),
      el("span", { class: "update-text", text: u.text || "" }),
    ]))));
  }

  const claims = rec.claims || [];
  children.push(detailSection(`Citations (${claims.length})`, claims.map(claimNode)));

  return el("article", { class: review ? "detail under-review" : "detail" }, children);
}

// Empty state for an active filter that matches nothing — distinct from the
// "nothing tracked yet" message loadPane shows for a genuinely empty dataset.
function noMatchNote() {
  return el("p", { class: "loading", text: "No records match the current filters." });
}

// --- Threats pane: grouped by category, severity-dominant ------------------
function renderThreats(records) {
  const st = viewState.threats;
  const filtered = records.filter((rec) =>
    (st.category === "all" || (rec.category || "other") === st.category) &&
    (st.severity === "all" || ((rec.assessment || {}).severity || "unknown") === st.severity));
  if (records.length && !filtered.length) return [noMatchNote()];

  const groups = new Map();
  for (const rec of filtered) {
    const cat = rec.category || "other";
    if (!groups.has(cat)) groups.set(cat, []);
    groups.get(cat).push(rec);
  }
  const cats = [...groups.keys()].sort((x, y) => {
    const ix = CATEGORY_ORDER.indexOf(x), iy = CATEGORY_ORDER.indexOf(y);
    return (ix === -1 ? 99 : ix) - (iy === -1 ? 99 : iy);
  });

  const out = [];
  for (const cat of cats) {
    const recs = groups.get(cat).sort((x, y) => compositeOf(y) - compositeOf(x));
    out.push(el("section", { class: "category" }, [
      el("h3", { class: "category-title", text: CATEGORY_LABELS[cat] || cat }),
      ...recs.map((r) => cardNode(r, { review: false, kind: "threat" })),
    ]));
  }
  return out;
}

// --- Pulse pane: recency-first with severity staying power ------------------
// Render-time ordering only: the stored sort_keys stay exactly as the pipeline
// computed them (pipeline/audit.py re-derives and enforces those), so the feed
// can weigh severity without touching any data file. Each impact tier above
// baseline buys two weeks of staying power; contained/resolved events decay
// ahead of ongoing ones. Known limit: a worsening long-running event keeps its
// original occurrence_date (the schema has no "latest development" date), so it
// rises only through its impact tier.
const SEVERITY_STAY_DAYS = 14;
const STATUS_DECAY_DAYS = { ongoing: 0, contained: 7, resolved: 14 };

function pulseOrderKey(rec) {
  const ev = rec.event || {};
  const t = Date.parse((ev.occurrence_date || "").slice(0, 10)); // date-only -> UTC midnight
  const days = Number.isFinite(t) ? t / 86400000 : 0;
  const impact = impactOf(rec) || 1;
  return days + SEVERITY_STAY_DAYS * (impact - 1) - (STATUS_DECAY_DAYS[ev.status] || 0);
}

function renderEvents(records) {
  const recs = records.slice().sort((x, y) =>
    (pulseOrderKey(y) - pulseOrderKey(x)) ||
    (impactOf(y) - impactOf(x)) ||
    (compositeOf(y) - compositeOf(x)));
  return recs.map((r) => cardNode(r, { review: false, kind: "event" }));
}

// --- History pane: grouped by era, chronological (oldest first by default) --
function renderHistorical(records) {
  const st = viewState.history;
  const newest = st.sort === "newest";
  const filtered = records.filter((rec) =>
    st.category === "all" || (rec.category || "other") === st.category);
  if (records.length && !filtered.length) return [noMatchNote()];

  const groups = new Map();
  for (const rec of filtered) {
    const era = (rec.historical || {}).era || "other";
    if (!groups.has(era)) groups.set(era, []);
    groups.get(era).push(rec);
  }
  const eras = [...groups.keys()].sort((x, y) => {
    const ix = ERA_ORDER.indexOf(x), iy = ERA_ORDER.indexOf(y);
    return (ix === -1 ? 99 : ix) - (iy === -1 ? 99 : iy);
  });
  if (newest) eras.reverse();

  const out = [];
  for (const era of eras) {
    const recs = groups.get(era).sort((x, y) =>
      (newest ? chronologyOf(y) - chronologyOf(x) : chronologyOf(x) - chronologyOf(y)) ||
      (impactOf(y) - impactOf(x)));
    out.push(el("section", { class: "category" }, [
      el("h3", { class: "category-title", text: ERA_LABELS[era] || era }),
      ...recs.map((r) => cardNode(r, { review: false, kind: "historical" })),
    ]));
  }
  return out;
}

function renderUnderReview(records, kind) {
  if (!records.length) return [];
  const noun = kind === "event" ? "events" : kind === "historical" ? "records" : "threats";
  return [el("section", { class: "review-section" }, [
    el("h3", { class: "category-title", text: "Under review" }),
    el("div", {
      class: "review-banner",
      text: `These ${noun} failed automated verification — no authoritative source has been ` +
            "confirmed for their headline claims. They are shown for transparency and must not " +
            "be read as established facts.",
    }),
    ...records.map((r) => cardNode(r, { review: true, kind })),
  ])];
}

// --- localStorage last-known-good (paint instantly, then revalidate) -------
function readCache(key) {
  try {
    const raw = localStorage.getItem(key);
    return raw ? JSON.parse(raw) : null;
  } catch (_) { return null; }
}

function writeCache(key, data) {
  try { localStorage.setItem(key, JSON.stringify(data)); } catch (_) { /* private mode */ }
}

async function loadPane({ url, mountId, freshnessId, kind, cacheKey, noun, staleAfterDays, onData }) {
  const mount = document.getElementById(mountId);
  const fresh = document.getElementById(freshnessId);
  let lastData = null;

  const render = (data) => {
    lastData = data;
    paneData[mountId] = data;
    const published = data.published || [];
    const underReview = data.under_review || [];
    const body = kind === "event" ? renderEvents(published)
      : kind === "historical" ? renderHistorical(published)
      : renderThreats(published);
    const nodes = [...body, ...renderUnderReview(underReview, kind)];
    if (!nodes.length) {
      mount.replaceChildren(el("p", { class: "loading", text: `No ${noun} tracked yet.` }));
    } else {
      mount.replaceChildren(...nodes);
    }
    if (onData) onData(data);
    // An open detail route over this pane repaints from the fresh data — this
    // is also how a cold deep link's "Loading…" placeholder resolves.
    const route = parseRoute();
    if (route.id && route.tab === mountId) renderDetail(route);
    if (!data.last_updated) {
      fresh.replaceChildren();
      return;
    }
    const summary = `${published.length} ${noun}${published.length === 1 ? "" : "s"}` +
      (underReview.length ? `, ${underReview.length} under review` : "") +
      ` · latest update ${dateOnly(data.last_updated)}`;
    const age = daysSince(data.last_updated);
    // staleAfterDays: null means the pane is exempt (an archive cannot go stale) —
    // without the isFinite guard, `age > null` would read as `age > 0`: always stale.
    const stale = Number.isFinite(age) && Number.isFinite(staleAfterDays) && age > staleAfterDays;
    const freshNodes = [el("span", { text: summary })];
    if (stale) {
      freshNodes.push(el("span", {
        class: "freshness-stale",
        text: ` — stale: no refresh in over ${Math.floor(age)} days (expected every ${staleAfterDays})`,
      }));
    }
    fresh.replaceChildren(...freshNodes);
  };

  // Toolbar changes re-render this pane from the latest data, no refetch.
  paneRerender[mountId] = () => { if (lastData) render(lastData); };

  const cached = readCache(cacheKey);
  if (cached) render(cached);

  try {
    const res = await fetch(`${url}?t=${Date.now()}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    writeCache(cacheKey, data);
    render(data);
  } catch (err) {
    if (!cached) {
      mount.replaceChildren(el("p", { class: "error", text: `Could not load ${noun}: ${err.message}` }));
    }
  }
}

// The values present in the data, in canonical order, unknowns appended — so the
// selects never offer a filter that matches nothing and need no schema knowledge.
function orderedUnique(values, canonical) {
  const present = new Set(values);
  const out = canonical.filter((v) => present.has(v));
  for (const v of present) if (!out.includes(v)) out.push(v);
  return out;
}

function fillSelect(id, values, labels) {
  const sel = document.getElementById(id);
  if (!sel) return;
  for (const v of values) {
    sel.appendChild(el("option", { value: v, text: (labels || {})[v] || v }));
  }
}

// Populate a pane's toolbar from its first data paint, then reveal it. Populating
// once keeps the user's selection stable across the cached->fresh double paint;
// a failed fetch simply leaves the toolbar hidden rather than showing dead UI.
function populateToolbar(barId, data, fill) {
  const bar = document.getElementById(barId);
  if (!bar || bar.dataset.ready) return;
  fill(data.published || []);
  bar.dataset.ready = "true";
  bar.hidden = false;
}

function setupToolbars() {
  const bind = (id, tab, key) => {
    const sel = document.getElementById(id);
    if (!sel) return;
    sel.addEventListener("change", () => {
      viewState[tab][key] = sel.value;
      if (paneRerender[tab]) paneRerender[tab]();
    });
  };
  bind("history-sort", "history", "sort");
  bind("history-category", "history", "category");
  bind("threats-category", "threats", "category");
  bind("threats-severity", "threats", "severity");
}

function main() {
  showView(parseRoute());
  window.addEventListener("hashchange", () => showView(parseRoute()));
  setupToolbars();

  // All three panes load eagerly: payloads are small, staleness banners stay live,
  // and switching tabs is instant with no fetch on first visit.
  loadPane({
    url: "./data/events.json", mountId: "pulse", freshnessId: "pulse-freshness",
    kind: "event", cacheKey: "globalobservatory.events", noun: "event", staleAfterDays: 2,
    onData: (data) => {
      if (window.GOMap) {
        GOMap.setEvents(data.published || [], { describe: (rec) => datelineText(rec, "event") });
      }
    },
  });
  loadPane({
    url: "./data/threats.json", mountId: "threats", freshnessId: "threats-freshness",
    kind: "threat", cacheKey: "globalobservatory.threats", noun: "tracked threat", staleAfterDays: 10,
    onData: (data) => populateToolbar("threats-toolbar", data, (recs) => {
      fillSelect("threats-category", orderedUnique(recs.map((r) => r.category || "other"), CATEGORY_ORDER), CATEGORY_LABELS);
      fillSelect("threats-severity",
        orderedUnique(recs.map((r) => (r.assessment || {}).severity || "unknown"), SEVERITY_ORDER));
    }),
  });
  loadPane({
    url: "./data/historical.json", mountId: "history", freshnessId: "history-freshness",
    kind: "historical", cacheKey: "globalobservatory.historical", noun: "historical record",
    staleAfterDays: null,
    onData: (data) => populateToolbar("history-toolbar", data, (recs) => {
      fillSelect("history-category",
        orderedUnique(recs.map((r) => r.category || "other"), Object.keys(HISTORICAL_TYPE_LABELS)),
        HISTORICAL_TYPE_LABELS);
    }),
  });
}

main();
