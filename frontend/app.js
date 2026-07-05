"use strict";

// --- Tabs (hash-routed) ------------------------------------------------------
// #pulse / #threats / #history are shareable URLs; back button walks tab history.
const TABS = ["pulse", "threats", "history"];

function currentTab() {
  const name = location.hash.replace(/^#/, "");
  return TABS.includes(name) ? name : "pulse"; // unknown hash -> default tab
}

function showTab(name) {
  for (const tab of TABS) {
    const pane = document.getElementById(`${tab}-pane`);
    if (pane) pane.hidden = tab !== name;
  }
  for (const link of document.querySelectorAll(".tabs a")) {
    const active = link.dataset.tab === name;
    link.classList.toggle("active", active);
    if (active) link.setAttribute("aria-current", "page");
    else link.removeAttribute("aria-current");
  }
  // A map laid out while its tab was hidden has zero size — re-measure on show.
  if (name === "pulse" && window.GOMap) GOMap.invalidate();
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

// --- Per-kind adapters: badge row + summary + meta -------------------------
function threatParts(rec, review) {
  const a = rec.assessment || {};
  const v = rec.verification || {};
  const prob = (a.probability || {}).estimate || "unknown";
  const sev = a.severity || "unknown";
  const badges = [
    review ? badge("under review", "badge-review")
           : badge(v.status || "unverified", `badge-${v.status || "unverified"}`),
    badge(`severity: ${sev}`, "badge-sev"),
    badge(`probability: ${prob}`, "badge-prob"),
    v.confidence ? badge(`confidence: ${v.confidence}`, "badge-conf") : null,
  ];
  const summary = a.summary || rec.description || "";
  const meta = [el("p", { class: "card-meta", text: `Last updated ${dateOnly(rec.last_updated)}` })];
  return { badges, summary, meta };
}

function eventParts(rec, review) {
  const ev = rec.event || {};
  const v = rec.verification || {};
  const status = ev.status || "ongoing";
  const loc = ev.location || {};
  const where = [loc.region, loc.country].filter(Boolean).join(", ");
  const badges = [
    review ? badge("under review", "badge-review")
           : badge(v.status || "unverified", `badge-${v.status || "unverified"}`),
    badge(EVENT_TYPE_LABELS[rec.category] || rec.category || "Event", "badge-cat"),
    badge(status, `badge-${status}`),
    ev.scale ? badge(ev.scale, "badge-scale") : null,
  ];
  const summary = (ev.impact || {}).summary || rec.description || "";

  const locLine = [where, dateOnly(ev.occurrence_date)].filter(Boolean).join(" · ");
  const meta = [];
  if (locLine) meta.push(el("p", { class: "card-loc", text: locLine }));
  if (ev.live_source_url) {
    const asOf = dateOnly(latestRetrievedDate(rec.claims)) || dateOnly(rec.last_updated);
    meta.push(el("p", { class: "card-live" }, [
      el("span", { text: `Figures as of ${asOf} — ` }),
      linkOut(ev.live_source_url, "live at source ↗"),
    ]));
  }
  return { badges, summary, meta };
}

function historicalParts(rec, review) {
  const hist = rec.historical || {};
  const v = rec.verification || {};
  const loc = hist.location || {};
  const where = [loc.region, loc.country].filter(Boolean).join(", ");
  const badges = [
    review ? badge("under review", "badge-review")
           : badge(v.status || "unverified", `badge-${v.status || "unverified"}`),
    badge(HISTORICAL_TYPE_LABELS[rec.category] || rec.category || "Event", "badge-cat"),
    hist.date_display ? badge(hist.date_display, "badge-scale") : null,
  ];
  const summary = (hist.impact || {}).summary || rec.description || "";
  const meta = [];
  if (where) meta.push(el("p", { class: "card-loc", text: where }));
  const deaths = formatDeathsRange(hist.impact || {});
  if (deaths) meta.push(el("p", { class: "card-meta", text: deaths }));
  return { badges, summary, meta };
}

function cardNode(rec, { review, kind }) {
  const parts = kind === "event" ? eventParts(rec, review)
    : kind === "historical" ? historicalParts(rec, review)
    : threatParts(rec, review);

  const head = el("div", { class: "card-head" }, [
    el("h3", { text: rec.name || rec.id }),
    el("div", { class: "badges" }, parts.badges),
  ]);

  const claims = rec.claims || [];
  const details = el("details", { class: "claims" }, [
    el("summary", { text: `${claims.length} cited claim${claims.length === 1 ? "" : "s"}` }),
    ...claims.map(claimNode),
  ]);

  // The id is the map's click-to-scroll target (see map.js).
  return el("article", { class: "card", id: `card-${rec.id}` }, [
    head,
    el("p", { class: "card-summary", text: parts.summary }),
    ...parts.meta,
    details,
  ]);
}

// --- Threats pane: grouped by category, severity-dominant ------------------
function renderThreats(records) {
  const groups = new Map();
  for (const rec of records) {
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

// --- Pulse pane: flat feed, recency-dominant -------------------------------
function renderEvents(records) {
  const recs = records.slice().sort((x, y) => compositeOf(y) - compositeOf(x));
  return recs.map((r) => cardNode(r, { review: false, kind: "event" }));
}

// --- History pane: grouped by era, chronological (oldest first) ------------
function renderHistorical(records) {
  const groups = new Map();
  for (const rec of records) {
    const era = (rec.historical || {}).era || "other";
    if (!groups.has(era)) groups.set(era, []);
    groups.get(era).push(rec);
  }
  const eras = [...groups.keys()].sort((x, y) => {
    const ix = ERA_ORDER.indexOf(x), iy = ERA_ORDER.indexOf(y);
    return (ix === -1 ? 99 : ix) - (iy === -1 ? 99 : iy);
  });

  const out = [];
  for (const era of eras) {
    const recs = groups.get(era).sort((x, y) =>
      (chronologyOf(x) - chronologyOf(y)) || (impactOf(y) - impactOf(x)));
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

  const render = (data) => {
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

function main() {
  showTab(currentTab());
  window.addEventListener("hashchange", () => showTab(currentTab()));

  // All three panes load eagerly: payloads are small, staleness banners stay live,
  // and switching tabs is instant with no fetch on first visit.
  loadPane({
    url: "./data/events.json", mountId: "pulse", freshnessId: "pulse-freshness",
    kind: "event", cacheKey: "globalobservatory.events", noun: "event", staleAfterDays: 2,
    onData: (data) => { if (window.GOMap) GOMap.setEvents(data.published || []); },
  });
  loadPane({
    url: "./data/threats.json", mountId: "threats", freshnessId: "threats-freshness",
    kind: "threat", cacheKey: "globalobservatory.threats", noun: "tracked threat", staleAfterDays: 10,
  });
  loadPane({
    url: "./data/historical.json", mountId: "history", freshnessId: "history-freshness",
    kind: "historical", cacheKey: "globalobservatory.historical", noun: "historical record",
    staleAfterDays: null,
  });
}

main();
