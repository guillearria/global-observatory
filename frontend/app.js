"use strict";
// Views consume the same generated aggregates as the daily publisher.
const datasets = {};
const currentYear = new Date().getUTCFullYear();
let historyMin = -2200,
  historyMax = currentYear;
function historyBounds(rows) {
  const years = rows
    .flatMap((r) => [r.historical?.year_start, r.historical?.year_end])
    .filter(Number.isFinite);
  const first = Math.min(-2199, ...years),
    last = Math.max(currentYear, ...years);
  return { min: first <= 0 ? first - 1 : first, max: last };
}
function freshness(kind, now = Date.now()) {
  const limit = { events: 2, threats: 10 }[kind];
  if (!limit) return "";
  const stamp = datasets[kind]?.last_updated,
    age = (now - Date.parse(stamp)) / 86400000;
  if (!Number.isFinite(age) || age < -1)
    return '<p class="notice" role="status">Collection refresh date is unavailable or invalid. Check original sources.</p>';
  return age > limit
    ? `<p class="notice" role="status">This collection has not been refreshed in ${Math.floor(age)} days. Check original sources for current information.</p>`
    : "";
}
async function loadDatasets(fetcher = fetch) {
  await Promise.all(
    ["events", "threats", "historical"].map(async (kind) => {
      try {
        const response = await fetcher(`./data/${kind}.json`, {
          cache: "no-cache",
        });
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const data = await response.json();
        if (!Array.isArray(data.published))
          throw new Error("Invalid collection");
        datasets[kind] = data;
      } catch (error) {
        datasets[kind] = { published: [], error: true };
        console.error(`Unable to load ${kind}`, error);
      }
    }),
  );
  const bounds = historyBounds(datasets.historical.published);
  historyMin = bounds.min;
  historyMax = bounds.max;
}

const main = document.querySelector("main");
const viewState = {};
const esc = (s) =>
  String(s ?? "").replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );
const safe = (url) => {
  try {
    const u = new URL(url);
    return u.protocol === "https:" ? u.href : "";
  } catch {
    return "";
  }
};
const ext = (url, label) =>
  safe(url)
    ? `<a href="${esc(safe(url))}" target="_blank" rel="noopener noreferrer">${esc(label)} <span aria-hidden="true">↗</span><span class="sr-only"> (opens in new tab)</span></a>`
    : `<span>${esc(label)}</span>`;
const date = (d) =>
  typeof d === "string" &&
  !d.startsWith("0000-") &&
  /^\d{4}-\d{2}-\d{2}$/.test(d) &&
  Number.isFinite(Date.parse(d)) &&
  new Date(d).toISOString().slice(0, 10) === d
    ? d
    : "";
const normalizedText = (s) =>
  String(s ?? "")
    .trim()
    .replace(/\s+/g, " ")
    .toLowerCase();
const excerpt = (s) =>
  s.length > 260
    ? (/\s/.test(s[260])
        ? s.slice(0, 260).trimEnd()
        : s.slice(0, 260).replace(/\s+\S*$/, "")) + "…"
    : s;
function sources(r) {
  const claims = r.claims || [];
  const unknown = claims.some(
    (c) => !date(c.retrieved_date) && c.retrieved_date !== "",
  );
  return `<details><summary>Evidence (${claims.length} claims)</summary>${unknown ? '<p class="small">Some retrieval dates are not recorded.</p>' : ""}<ol class="sources">${claims.map((c) => `<li><p>${esc(c.text)}</p>${ext(c.source_url, c.source_name || "Source")} ${date(c.retrieved_date) ? `<span class="small">Retrieved ${esc(c.retrieved_date)}</span>` : c.retrieved_date === "" ? '<span class="small">Source never retrieved</span>' : ""}${c.retrieval_note ? `<p class="small">${esc(c.retrieval_note)}</p>` : ""}${c.verification_status !== "verified" ? `<p class="status-warning">${esc(label(c.verification_status || "unverified"))}</p>` : ""}</li>`).join("")}</ol></details>`;
}
const helpPages = [
  {
    place: "Sudan",
    operator: "World Food Programme",
    scope: "Food assistance · Sudan-wide response",
    url: "https://www.wfp.org/emergencies/sudan",
    ids: [
      "sudan-displacement-crisis",
      "el-obeid-siege-sudan-2026",
      "sudan-drone-strikes-kordofan-abyei-2026",
    ],
  },
  {
    place: "Haiti",
    operator: "World Food Programme",
    scope: "Food and cash assistance · Includes people displaced by violence",
    url: "https://www.wfp.org/emergencies/haiti-emergency",
    ids: ["haiti-gang-violence-displacement-2026"],
  },
  {
    place: "Eastern DR Congo",
    operator: "UNICEF",
    scope: "Water, health and protection for children · Eastern DRC",
    url: "https://www.unicef.org/drcongo/en/what-we-do/emergency-response/eastern-drc",
    ids: ["drc-north-kivu-ituri-displacement-2026"],
  },
  {
    place: "Yemen",
    operator: "World Food Programme",
    scope: "Food assistance · Includes people displaced by recent fighting",
    url: "https://www.wfp.org/emergencies/yemen-emergency",
    ids: ["yemen-conflict-escalation-2026"],
  },
];
const helpFor = (id) => helpPages.filter((p) => p.ids.includes(id));
const year = (n) => (n <= 0 ? `${1 - n} BCE` : `${n} CE`);
const toStoredYear = (n) => (n < 0 ? n + 1 : n);
const endYear = (h) =>
  Number.isFinite(h.year_end)
    ? h.year_end
    : /\bpresent\b/i.test(h.date_display || "")
      ? currentYear
      : null;
const validLocation = (r) => {
  const l = r.event?.location || r.historical?.location;
  return (
    l &&
    Number.isFinite(l.lat) &&
    Number.isFinite(l.lon) &&
    Math.abs(l.lat) <= 90 &&
    Math.abs(l.lon) <= 180
  );
};
const bucket = (n) =>
  typeof n !== "number" || !Number.isFinite(n) || n < 0
    ? "unknown"
    : n === 0
      ? "zero"
      : n < 100
        ? "small"
        : n < 1000
          ? "medium"
          : "large";
const yearMatch = (r, lo, hi) => {
  const h = r.historical;
  return (
    Number.isFinite(h.year_start) &&
    h.year_start <= hi &&
    (endYear(h) !== null ? endYear(h) >= lo : h.year_start >= lo)
  );
};
const historicalOrder = (a, b) =>
  a.historical.year_start - b.historical.year_start || a.id.localeCompare(b.id);
const label = (s) =>
  String(s ?? "")
    .replaceAll("-", " ")
    .replace(/(^|\s)\p{Ll}/gu, (c) => c.toUpperCase());
const iconPaths = {
  plus: "M12 5v14M5 12h14",
  minus: "M5 12h14",
  reset: "M4 10a8 8 0 1 1 1 8M4 4v6h6",
  left: "m14 6-6 6 6 6",
  right: "m10 6 6 6-6 6",
  up: "m6 14 6-6 6 6",
  down: "m6 10 6 6 6-6",
  biological: "M8 3c0 9 8 9 8 18M16 3c0 9-8 9-8 18M8 5h8M9 9h6M9 15h6M8 19h8",
  climate: "M13 3v11a4 4 0 1 1-4 0V3a2 2 0 0 1 4 0M11 8v9M17 5h3M17 9h2",
  cosmic:
    "M12 2v4M12 18v4M2 12h4M18 12h4M5 5l3 3M16 16l3 3M5 19l3-3M16 8l3-3M15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0",
  geological: "m2 20 7-15 5 9 3-5 5 11H2M6 12l3 2 3-3",
  nuclear:
    "M12 10a2 2 0 1 1 0 4 2 2 0 0 1 0-4M10 7 8 3a10 10 0 0 1 8 0l-2 4M7 13l-5 1a10 10 0 0 0 4 7l3-4M17 13l5 1a10 10 0 0 1-4 7l-3-4",
  resource: "M12 21V11M12 16C3 16 3 8 3 8s9-1 9 8M12 12c0-9 9-9 9-9s1 9-9 9",
  societal:
    "M8 8a3 3 0 1 1 0-6 3 3 0 0 1 0 6M16 10a3 3 0 1 1 0-6 3 3 0 0 1 0 6M2 21v-5a6 6 0 0 1 12 0v5M15 13a6 6 0 0 1 7 6v2",
  technological:
    "M7 7h10v10H7zM9 2v5M15 2v5M9 17v5M15 17v5M2 9h5M2 15h5M17 9h5M17 15h5",
};
const icon = (name) =>
  `<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="${Object.hasOwn(iconPaths, name) ? iconPaths[name] : iconPaths.cosmic}"/></svg>`;
function helpCard(p) {
  return `<p class="meta">${esc(p.place)}</p><h3>${esc(p.operator)}</h3><p>${esc(p.scope)}</p>${ext(p.url, "Response and ways to give")}<p class="small">Broader response, not a fund for this individual incident.</p>`;
}
function helpBlock(id) {
  const pages = helpFor(id);
  return `<aside class="help"><h2>How to help</h2>${pages.length ? pages.map(helpCard).join("") : '<p>No response link reviewed for this event yet.</p><a href="#about">Suggest a relevant organization</a>'}<p class="small">${pages.length ? "Pages checked 4 Nov 2026. Links are not endorsements; check the organization’s donation terms." : ""}</p></aside>`;
}
let carouselIndex = 0;
function carousel() {
  return `<aside class="help carousel" role="region" aria-roledescription="carousel" aria-labelledby="help-heading"><h2 id="help-heading">Ways to help</h2><div class="carousel-stage"><button id="previous" class="carousel-arrow" aria-label="Previous response">${icon("left")}</button><div id="slide" role="group" aria-live="polite" aria-atomic="true"></div><button id="next" class="carousel-arrow" aria-label="Next response">${icon("right")}</button></div><div class="slide-nav">${helpPages.map((p, i) => `<button data-slide="${i}" aria-label="${esc(p.place)}: slide ${i + 1} of ${helpPages.length}" aria-current="${i === carouselIndex ? "true" : "false"}"><span></span></button>`).join("")}<span id="slide-count" class="sr-only"></span></div></aside>`;
}
function bindCarousel() {
  function paint() {
    const p = helpPages[carouselIndex];
    document
      .querySelector("#slide")
      .setAttribute(
        "aria-label",
        `${carouselIndex + 1} of ${helpPages.length}`,
      );
    document.querySelector("#slide").innerHTML =
      `<a class="response-card" href="${esc(p.url)}" target="_blank" rel="noopener noreferrer" aria-label="${esc(p.place + " — " + p.operator + ". " + p.scope + ". Official response page; check donation terms. Opens in a new tab.")}"><span class="response-icon" aria-hidden="true">${esc(
        p.operator === "UNICEF"
          ? "U"
          : p.operator
              .split(/\s+/)
              .map((w) => w[0])
              .join(""),
      )}</span><span class="response-text"><strong>${esc(p.place)}</strong><span>${esc(p.operator)}</span></span><span class="response-external" aria-hidden="true">↗</span></a>`;
    document.querySelector("#slide-count").textContent =
      `${carouselIndex + 1} / ${helpPages.length}`;
    document
      .querySelectorAll("[data-slide]")
      .forEach((b) =>
        b.setAttribute(
          "aria-current",
          String(Number(b.dataset.slide) === carouselIndex),
        ),
      );
  }
  document.querySelectorAll("[data-slide]").forEach(
    (b) =>
      (b.onclick = () => {
        carouselIndex = Number(b.dataset.slide);
        paint();
      }),
  );
  document.querySelector("#previous").onclick = () => {
    carouselIndex = (carouselIndex + helpPages.length - 1) % helpPages.length;
    paint();
  };
  document.querySelector("#next").onclick = () => {
    carouselIndex = (carouselIndex + 1) % helpPages.length;
    paint();
  };
  paint();
}
let disposeMap = () => {};
function mountMap(host, records, onSelect, { passive = false } = {}) {
  const points = records.filter(validLocation);
  let zoom = 1,
    x = 0,
    y = 0,
    active = 0;
  const groups = [];
  for (const r of points) {
    const l = r.event?.location || r.historical.location;
    let g = groups.find((g) => g.lat === l.lat && g.lon === l.lon);
    if (!g) {
      g = { lat: l.lat, lon: l.lon, records: [] };
      groups.push(g);
    }
    g.records.push(r);
  }
  host.innerHTML = `<div class="map-tools"><div class="control-group" role="group" aria-label="Map zoom"><button data-map="out" aria-label="Zoom out">${icon("minus")}</button><span data-map="zoom" aria-live="polite">1×</span><button data-map="in" aria-label="Zoom in">${icon("plus")}</button></div><button data-map="reset" class="reset-map">${icon("reset")}<span>World view</span></button><div class="control-group pan-controls" role="group" aria-label="Pan map">${["left", "up", "down", "right"].map((dir) => `<button data-pan="${dir}" aria-label="Pan ${dir}">${icon(dir)}</button>`).join("")}</div></div><div class="world" role="region" tabindex="0" aria-label="World map" aria-describedby="map-help"><div class="earth"><img src="./assets/blue-marble-4096.jpg" alt="" draggable="false">${groups
    .map((g, i) => {
      const b = passive
        ? "location"
        : g.records.length > 1
          ? "cluster"
          : bucket(g.records[0].event?.impact?.deaths);
      return `<${passive ? "span" : "button"} class="marker ${b}" style="left:${((g.lon + 180) / 360) * 100}%;top:${((90 - g.lat) / 180) * 100}%" data-index="${i}" ${passive ? 'aria-hidden="true"' : `tabindex="${i === 0 ? 0 : -1}" aria-pressed="false"`} aria-label="${esc(g.records.length > 1 ? g.records.length + " events at this location: " + g.records.map((r) => r.name).join("; ") : g.records[0].name + " · " + (passive ? "approximate location" : b === "unknown" ? "deaths not recorded" : g.records[0].event.impact.deaths + " recorded deaths"))}"><span>${g.records.length > 1 ? g.records.length : ""}</span></${passive ? "span" : "button"}>`;
    })
    .join(
      "",
    )}</div></div><details class="map-legend"><summary>What the dots mean </summary><p id="map-help" class="small">Approximate locations, not affected areas. Basemap: NASA Blue Marble. Drag with a mouse or use the pan controls; arrow keys browse focused markers. Recorded deaths, not importance: <i class="legend-dot unknown"></i> unknown · <i class="legend-dot zero"></i> 0 · <i class="legend-dot small"></i> 1–99 · <i class="legend-dot medium"></i> 100–999 · <i class="legend-dot large"></i> 1,000+. Numbers on markers group records at identical coordinates. Figures are saved snapshots; a small dot may still represent a major crisis. Use the list to reach overlapping locations.</p></details>`;
  const world = host.querySelector(".world"),
    earth = host.querySelector(".earth"),
    markers = [...host.querySelectorAll(".marker")];
  const abort = new AbortController();
  const listen = (el, type, fn) =>
    el.addEventListener(
      type,
      (e) => {
        if (type === "click" && el.getAttribute("aria-disabled") === "true")
          return;
        fn(e);
      },
      { signal: abort.signal },
    );
  function render() {
    const w = world.clientWidth,
      h = world.clientHeight,
      bw = w,
      bh = bw / 2;
    const maxX = Math.max(0, (bw * zoom - w) / 2),
      maxY = Math.max(0, (bh * zoom - h) / 2);
    x = Math.max(-maxX, Math.min(maxX, x));
    y = Math.max(-maxY, Math.min(maxY, y));
    earth.style.width = bw + "px";
    earth.style.height = bh + "px";
    earth.style.transform = `translate(calc(-50% + ${x}px),calc(-50% + ${y}px)) scale(${zoom})`;
    earth.style.setProperty("--unzoom", 1 / zoom);
    host.querySelector('[data-map="zoom"]').textContent = zoom.toFixed(1) + "×";
    host.querySelectorAll("[data-pan]").forEach((b) => {
      b.setAttribute(
        "aria-disabled",
        String(
          {
            left: x >= maxX,
            right: x <= -maxX,
            up: y >= maxY,
            down: y <= -maxY,
          }[b.dataset.pan],
        ),
      );
    });
    host
      .querySelector('[data-map="out"]')
      .setAttribute("aria-disabled", String(zoom <= 1));
    host
      .querySelector('[data-map="in"]')
      .setAttribute("aria-disabled", String(zoom >= 8));
  }
  function change(n) {
    n = Math.max(1, Math.min(8, n));
    x *= n / zoom;
    y *= n / zoom;
    zoom = n;
    render();
  }
  listen(host.querySelector('[data-map="in"]'), "click", () =>
    change(zoom * 1.5),
  );
  listen(host.querySelector('[data-map="out"]'), "click", () =>
    change(zoom / 1.5),
  );
  listen(host.querySelector('[data-map="reset"]'), "click", () => {
    zoom = 1;
    x = y = 0;
    render();
  });
  function select(i) {
    active = i;
    markers.forEach((m, j) => {
      m.tabIndex = j === i ? 0 : -1;
      m.setAttribute("aria-pressed", String(j === i));
    });
    onSelect(groups[i].records);
  }
  markers.forEach((m, i) => {
    if (passive) return;
    listen(m, "focus", () => {
      const a = m.getBoundingClientRect(),
        b = world.getBoundingClientRect();
      if (
        a.left < b.left ||
        a.right > b.right ||
        a.top < b.top ||
        a.bottom > b.bottom
      ) {
        const g = groups[i],
          bw = world.clientWidth;
        x = -(g.lon / 360) * bw * zoom;
        y = (g.lat / 180) * (bw / 2) * zoom;
        render();
      }
    });
    listen(m, "click", () => select(i));
    listen(m, "keydown", (e) => {
      if (["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown"].includes(e.key)) {
        e.preventDefault();
        e.stopPropagation();
        active =
          (i +
            (["ArrowLeft", "ArrowUp"].includes(e.key)
              ? markers.length - 1
              : 1)) %
          markers.length;
        markers.forEach((m, j) => (m.tabIndex = j === active ? 0 : -1));
        const g = groups[active],
          bw = world.clientWidth;
        x = -(g.lon / 360) * bw * zoom;
        y = (g.lat / 180) * (bw / 2) * zoom;
        render();
        markers[active].focus();
      }
    });
  });
  listen(world, "keydown", (e) => {
    if (e.target !== world) return;
    const moves = {
      ArrowLeft: [50, 0],
      ArrowRight: [-50, 0],
      ArrowUp: [0, 50],
      ArrowDown: [0, -50],
    };
    if (moves[e.key]) {
      e.preventDefault();
      x += moves[e.key][0];
      y += moves[e.key][1];
      render();
    } else if (["+", "=", "-"].includes(e.key)) {
      e.preventDefault();
      change(zoom * (e.key === "-" ? 1 / 1.5 : 1.5));
    }
  });
  host.querySelectorAll("[data-pan]").forEach((b) =>
    listen(b, "click", () => {
      const dx = world.clientWidth * 0.25,
        dy = world.clientHeight * 0.25,
        d = { left: [dx, 0], right: [-dx, 0], up: [0, dy], down: [0, -dy] }[
          b.dataset.pan
        ];
      x += d[0];
      y += d[1];
      render();
    }),
  );
  let start;
  listen(world, "pointerdown", (e) => {
    if (e.pointerType !== "mouse" || e.target.closest("button")) return;
    start = { id: e.pointerId, x: e.clientX, y: e.clientY, ox: x, oy: y };
    world.setPointerCapture(e.pointerId);
  });
  listen(world, "pointermove", (e) => {
    if (start && start.id === e.pointerId) {
      x = start.ox + e.clientX - start.x;
      y = start.oy + e.clientY - start.y;
      render();
    }
  });
  listen(world, "pointerup", () => (start = null));
  listen(world, "pointercancel", () => (start = null));
  const resize = new ResizeObserver(render);
  resize.observe(world);
  if (passive) {
    host.querySelector(".map-legend").innerHTML =
      '<summary>Map details</summary><p id="map-help" class="small">Approximate location, not an affected-area boundary. Basemap: NASA Blue Marble. Use the controls to zoom and pan.</p>';
    if (groups.length === 1) {
      zoom = 3;
      const bw = world.clientWidth;
      x = (-groups[0].lon / 360) * bw * zoom;
      y = (groups[0].lat / 180) * (bw / 2) * zoom;
    }
  }
  render();
  return () => {
    abort.abort();
    resize.disconnect();
  };
}
function row(r, kind) {
  const d = r.event || r.historical || {};
  return `<article class="row"><div class="place">${esc(kind === "historical" ? d.date_display || year(d.year_start) : d.location?.country || label(r.category))}<div class="status">${esc(label(d.status || d.era || ""))}</div></div><h3><a href="#${kind}/${encodeURIComponent(r.id)}">${esc(r.name)}</a></h3></article>`;
}
function eventListing() {
  let mapKey = null;
  const state =
    viewState.events ||
    (viewState.events = {
      query: "",
      status: "ongoing",
      country: "",
      help: false,
      limit: 8,
    });
  main.innerHTML = `<h1>Explore what’s happening.</h1><p class="intro">A world of events, with context and ways to help.</p><div class="explorer"><section><div class="map-surface"><div id="world-map"></div><div id="selection" class="selection" aria-live="polite"><h2>Choose a point on the map</h2><p class="small">Select a marker to explore an event.</p></div></div></section></div>${carousel()}<div class="section-head"><h2>Explore emergencies</h2><span id="count" role="status"></span></div><div class="toolbar"><input id="search" type="search" aria-label="Search emergencies" placeholder="Find a place or event"><select id="status" aria-label="Status"><option value="ongoing">Ongoing</option><option value="all">All statuses</option><option value="contained">Contained</option><option value="resolved">Resolved</option></select><select id="country" aria-label="Country"><option value="">All countries</option>${[
    ...new Set(
      datasets.events.published
        .map((r) => r.event?.location?.country)
        .filter(Boolean),
    ),
  ]
    .sort()
    .map((c) => `<option value="${esc(c)}">${esc(c)}</option>`)
    .join(
      "",
    )}</select><label><input type="checkbox" id="help-only"> Ways to help available</label></div><div id="rows"></div><button id="more">Show more</button><p class="footnote">Collection snapshot: ${esc((datasets.events.last_updated || "").slice(0, 10))}. Browse sources before relying on figures.</p>`;
  bindCarousel();
  function select(records) {
    document.querySelector("#selection").innerHTML = records
      .map(
        (r) =>
          `<div class="selected-event"><div><p class="meta">${esc(r.event.location.country)} · ${esc(label(r.event.status))}</p><h2>${esc(r.name)}</h2><p class="selection-summary">${esc(excerpt(r.description || r.event?.summary || ""))}</p><p class="small">${bucket(r.event.impact?.deaths) === "unknown" ? "Deaths not recorded" : Number(r.event.impact.deaths).toLocaleString() + " recorded deaths"} · Approximate location</p></div><div class="selection-action"><a class="primary" href="#events/${encodeURIComponent(r.id)}">View event ${icon("right")}</a></div></div>`,
      )
      .join("<hr>");
  }
  function paint(resetMap = true) {
    let rows = datasets.events.published.filter(
      (r) =>
        (state.status === "all" || r.event?.status === state.status) &&
        (!state.country || r.event?.location?.country === state.country) &&
        (!state.help || helpFor(r.id).length) &&
        [r.name, r.event?.location?.country]
          .join(" ")
          .toLowerCase()
          .includes(state.query.toLowerCase()),
    );
    document.querySelector("#count").textContent = rows.length + " records";
    document.querySelector("#rows").innerHTML =
      rows
        .slice(0, state.limit)
        .map((r) => row(r, "events"))
        .join("") || "<p>No matching records.</p>";
    document.querySelector("#more").hidden = rows.length <= state.limit;
    const key = rows.map((r) => r.id).join("|");
    if (resetMap && key !== mapKey) {
      mapKey = key;
      document.querySelector(".map-surface > .map-legend")?.remove();
      document.querySelector("#selection").innerHTML =
        '<div class="selection-empty"><p class="meta">Explore the world</p><h2>Select an event</h2><p class="small">Choose a marker to see its context and sources.</p></div>';
      disposeMap();
      disposeMap = mountMap(document.querySelector("#world-map"), rows, select);
      const legend = document.querySelector("#world-map .map-legend");
      document.querySelector(".map-surface").appendChild(legend);
    }
  }
  for (const key of ["search", "status", "country", "help-only"]) {
    const el = document.getElementById(key);
    const prop = {
      search: "query",
      status: "status",
      country: "country",
      "help-only": "help",
    }[key];
    if (el.type === "checkbox") el.checked = state[prop];
    else el.value = state[prop];
    el.addEventListener(key === "search" ? "input" : "change", () => {
      state[prop] = el.type === "checkbox" ? el.checked : el.value;
      state.limit = 8;
      paint();
    });
  }
  document.querySelector("#more").onclick = () => {
    const n = state.limit;
    state.limit += 8;
    paint(false);
    document.querySelectorAll("#rows h3 a")[n]?.focus();
  };
  paint();
}
function historyView() {
  const rows = datasets.historical.published;
  const state =
    viewState.historical ||
    (viewState.historical = {
      lo: historyMin,
      hi: historyMax,
      era: "",
      category: "",
      sort: "old",
      query: "",
    });
  const options = (field) =>
    [...new Set(rows.map((r) => field(r)))]
      .sort()
      .map((v) => `<option value="${esc(v)}">${esc(label(v))}</option>`)
      .join("");
  main.innerHTML = `<h1>Explore the past.</h1><p class="intro">Move through centuries of disasters, disease and conflict.</p><section class="timeline-controls"><div class="toolbar"><label>From <input id="from" aria-describedby="year-help history-count" type="number" min="${historyMin}" max="${historyMax}" value="${state.lo}"></label><label>To <input id="to" aria-describedby="year-help history-count" type="number" min="${historyMin}" max="${historyMax}" value="${state.hi}"></label></div><div class="history-presets" role="group" aria-label="History date presets"><button id="all-years">All years</button><button data-range="${historyMin},-1">BCE</button><button data-range="1,1499">1–1499 CE</button><button data-range="1500,${historyMax}">Since 1500</button><button id="recent-years">Since 1900</button><button data-range="2000,${historyMax}">Since 2000</button></div><p class="sr-only" id="year-help">Enter negative numbers for BCE and positive numbers for CE. There is no year zero.</p><label for="time-start">Trim earlier years</label><input id="time-start" type="range" min="${toStoredYear(historyMin)}" max="${toStoredYear(state.hi)}" value="${toStoredYear(state.lo)}"><div class="toolbar"><select id="era" aria-label="Period"><option value="">All periods</option>${options((r) => r.historical.era)}</select><select id="category" aria-label="Category"><option value="">All categories</option>${options((r) => r.category)}</select><select id="sort" aria-label="Date order"><option value="old">Oldest first</option><option value="new">Newest first</option></select><input id="history-search" type="search" placeholder="Search history" aria-label="Search history"></div><p id="history-count" role="status"></p></section><div id="timeline"></div><details><summary>How dates work</summary><p class="footnote">Filters include overlapping recorded ranges. Unknown ends match the start year only. Dates and period labels follow the saved collection. Bars show recorded year ranges on a linear scale; explicit ongoing records extend to ${currentYear}, and unknown ends appear as points. Stored astronomical years are converted to BCE/CE. Period boundaries vary across regions.</p></details>`;
  function paint() {
    const from = document.querySelector("#from"),
      to = document.querySelector("#to");
    if (from.value === "" || to.value === "") {
      document.querySelector("#timeline").innerHTML = "";
      document
        .querySelectorAll(".history-presets button")
        .forEach((b) => b.setAttribute("aria-pressed", "false"));
      return;
    }
    const lo = Number(from.value),
      hi = Number(to.value);
    const slider = document.querySelector("#time-start");
    if (
      !Number.isInteger(lo) ||
      !Number.isInteger(hi) ||
      lo === 0 ||
      hi === 0 ||
      lo > hi ||
      lo < historyMin ||
      hi > historyMax
    ) {
      document.querySelector("#history-count").textContent =
        `Choose a valid range between ${year(toStoredYear(historyMin))} and ${year(historyMax)}, excluding year zero.`;
      document.querySelector("#timeline").innerHTML = "";
      document
        .querySelectorAll(".history-presets button")
        .forEach((b) => b.setAttribute("aria-pressed", "false"));
      from.setAttribute("aria-invalid", "true");
      to.setAttribute("aria-invalid", "true");
      return;
    }
    from.removeAttribute("aria-invalid");
    to.removeAttribute("aria-invalid");
    state.lo = lo;
    state.hi = hi;
    slider.max = toStoredYear(hi);
    slider.value = toStoredYear(lo);
    slider.setAttribute("aria-valuetext", year(toStoredYear(lo)));
    document.querySelectorAll(".history-presets button").forEach((b) => {
      const range =
        b.id === "all-years"
          ? [historyMin, historyMax]
          : b.id === "recent-years"
            ? [1900, historyMax]
            : b.dataset.range.split(",").map(Number);
      b.setAttribute(
        "aria-pressed",
        String(range[0] === lo && range[1] === hi),
      );
    });
    let matches = rows
      .filter(
        (r) =>
          yearMatch(r, toStoredYear(lo), toStoredYear(hi)) &&
          (!state.era || r.historical.era === state.era) &&
          (!state.category || r.category === state.category) &&
          r.name.toLowerCase().includes(state.query.toLowerCase()),
      )
      .sort(historicalOrder);
    if (state.sort === "new") matches.reverse();
    document.querySelector("#history-count").textContent =
      `${matches.length} records · ${year(toStoredYear(lo))} → ${year(toStoredYear(hi))}`;
    const axisLo = toStoredYear(lo),
      axisHi = toStoredYear(hi),
      span = Math.max(1, axisHi - axisLo);
    document.querySelector("#timeline").innerHTML =
      `<div class="axis"><span>${year(axisLo)}</span><span>${year(axisHi)}</span></div>` +
      matches
        .map((r) => {
          const h = r.historical,
            left = Math.max(0, ((h.year_start - axisLo) / span) * 100),
            end = Math.min(
              100,
              (((endYear(h) ?? h.year_start) - axisLo) / span) * 100,
            );
          return `<article class="timeline-row"><p class="meta">${esc(h.date_display || year(h.year_start))} · ${esc(label(h.era))}</p><div class="time-track" aria-hidden="true"><span style="left:min(${left}%, calc(100% - 8px));width:${Math.max(0, end - left)}%"></span></div><h3><a href="#historical/${encodeURIComponent(r.id)}">${esc(r.name)}</a></h3>${endYear(h) === null ? '<span class="small">End not recorded</span>' : /\bpresent\b/i.test(h.date_display || "") ? '<span class="small">Ongoing · shown to current year</span>' : ""}</article>`;
        })
        .join("");
  }
  for (const key of ["era", "category", "sort"]) {
    const el = document.getElementById(key);
    el.value = state[key];
    el.onchange = () => {
      state[key] = el.value;
      paint();
    };
  }
  document.querySelector("#history-search").value = state.query;
  document.querySelector("#history-search").oninput = (e) => {
    state.query = e.target.value;
    paint();
  };
  for (const id of ["from", "to"]) document.getElementById(id).oninput = paint;
  document.querySelector("#time-start").oninput = (e) => {
    const n = Number(e.target.value);
    document.querySelector("#from").value = n <= 0 ? n - 1 : n;
    paint();
  };
  document.querySelectorAll("[data-range]").forEach(
    (b) =>
      (b.onclick = () => {
        const [a, z] = b.dataset.range.split(",").map(Number);
        setRange(a, z);
      }),
  );
  document.querySelector("#all-years").onclick = () =>
    setRange(historyMin, historyMax);
  document.querySelector("#recent-years").onclick = () =>
    setRange(1900, historyMax);
  function setRange(a, b) {
    document.querySelector("#from").value = a;
    document.querySelector("#to").value = b;
    paint();
  }
  paint();
}
function riskVisual(r) {
  const a = r.assessment || {};
  const levels = ["regional", "continental", "civilizational"];
  return `<div class="risk-visual"><p class="meta">Potential scale · Collection assessment</p>${!levels.includes(a.severity) ? `<p>Scale: ${esc(label(a.severity || "not assessed"))}</p>` : ""}<div class="severity">${levels.map((v) => `<span class="${a.severity === v ? "chosen" : ""}">${a.severity === v ? "✓ " : ""}${label(v)}${a.severity === v ? '<span class="sr-only"> (selected assessment)</span>' : ""}</span>`).join("")}</div><p><strong>Likelihood:</strong> ${esc(label(a.probability?.estimate || "Not estimated"))}<br><span class="small">${esc(label(a.probability?.window || "No time window recorded"))}</span></p><p class="small">Qualitative labels, not a forecast. See the evidence below.</p></div>`;
}
function risks() {
  const rows = datasets.threats.published;
  const categories = [...new Set(rows.map((r) => r.category))].sort();
  main.innerHTML = `<h1>Risks</h1><p class="intro">Explore possible consequences and the evidence behind them.</p><h2 class="category-heading">Categories</h2><div class="risk-grid">${categories.map((c) => `<button class="risk-category" data-category="${esc(c)}" aria-pressed="false">${icon(c)}<span>${esc(label(c))}</span></button>`).join("")}</div><div class="toolbar"><select id="risk-filter" aria-label="Risk category"><option value="">All categories</option>${categories.map((c) => `<option value="${esc(c)}">${esc(label(c))}</option>`).join("")}</select><input id="risk-search" type="search" aria-label="Search risks" placeholder="Search risks"></div><p id="risk-count" role="status"></p><div id="risk-rows"></div>`;
  const filter = document.querySelector("#risk-filter"),
    search = document.querySelector("#risk-search");
  function paint() {
    const matches = rows.filter(
      (r) =>
        (!filter.value || r.category === filter.value) &&
        r.name.toLowerCase().includes(search.value.toLowerCase()),
    );
    document.querySelector("#risk-count").textContent =
      matches.length + " records";
    document
      .querySelectorAll("[data-category]")
      .forEach((b) =>
        b.setAttribute(
          "aria-pressed",
          String(b.dataset.category === filter.value),
        ),
      );
    document.querySelector("#risk-rows").innerHTML =
      matches.map((r) => row(r, "threats")).join("") ||
      "<p>No matching records.</p>";
  }
  filter.onchange = paint;
  search.oninput = paint;
  document.querySelectorAll("[data-category]").forEach(
    (b) =>
      (b.onclick = () => {
        filter.value =
          filter.value === b.dataset.category ? "" : b.dataset.category;
        paint();
      }),
  );
  paint();
}
function recordFacts(r) {
  const d = r.event || {};
  const latest = (r.claims || [])
    .map((c) => date(c.retrieved_date))
    .filter(Boolean)
    .sort()
    .at(-1);
  const facts = [];
  if (latest) facts.push(`Latest dated source retrieval ${esc(latest)}`);
  if (d.occurrence_date) facts.push(`Started ${esc(d.occurrence_date)}`);
  if (d.scale) facts.push(esc(d.scale));
  for (const [key, label] of [
    ["deaths", "Recorded deaths"],
    ["displaced", "Recorded displaced"],
  ]) {
    if (Number.isFinite(d.impact?.[key]))
      facts.push(`${label}: ${d.impact[key].toLocaleString()}`);
  }
  return `<section class="record-facts"><p class="small">${facts.join(" · ")}</p>${safe(d.live_source_url) ? ext(d.live_source_url, "Latest at source") : ""}</section>`;
}
function recordUpdates(r) {
  return r.updates?.length
    ? `<details><summary>Updates (${r.updates.length})</summary><ol class="sources">${r.updates.map((u) => `<li><time>${esc(u.date)}</time><p>${esc(u.text)}</p></li>`).join("")}</ol></details>`
    : "";
}
function record(kind, id) {
  const r = datasets[kind].published.find((r) => r.id === id);
  if (!r) {
    main.innerHTML = "<h1>Record not found</h1>";
    return;
  }
  const d = r.event || r.historical || r.assessment || {};
  main.innerHTML = `<a class="back" href="#${kind}">← Back to collection</a><header class="detail-header"><p class="meta">${esc(d.location?.country || label(r.category))}${d.date_display ? " · " + esc(d.date_display) : ""}</p><h1>${esc(r.name)}</h1><p class="small">Record edited ${esc((r.last_updated || "").slice(0, 10))} · Automated summary</p></header><div class="detail-layout"><section><div id="detail-visual"></div><div class="full-overview"><h2>Overview</h2><p>${esc(r.description || d.summary || "")}</p></div></section>${kind === "events" ? helpBlock(id) : ""}</div>${d.impact?.summary && normalizedText(d.impact.summary) !== normalizedText(r.description || d.summary) ? `<section class="impact-context"><h2>Impact and context</h2><p class="prose">${esc(d.impact.summary)}</p></section>` : ""}${kind === "threats" && d.summary && normalizedText(d.summary) !== normalizedText(r.description) ? `<section class="impact-context"><h2>Assessment context</h2><p>${esc(d.summary)}</p></section>` : ""}${d.timeframe ? `<section class="impact-context"><h2>Timeframe</h2><p class="prose">${esc(d.timeframe)}</p></section>` : ""}${recordFacts(r)}${recordUpdates(r)}${sources(r)}`;
  const visual = document.querySelector("#detail-visual");
  if (kind === "historical")
    visual.innerHTML = `<div class="date-visual"><span>${esc(label(d.era))}</span><strong>${esc(d.date_display || year(d.year_start))}</strong><div class="date-line" aria-hidden="true">●━━━━━━━━${d.year_end != null ? "●" : "┄"}</div><p class="small">${year(d.year_start)}${endYear(d) !== null ? " → " + (/\bpresent\b/i.test(d.date_display || "") ? `present (${currentYear})` : year(endYear(d))) : " · End not recorded"} · Date context, not a geographic location</p></div>`;
  else if (kind === "threats") visual.innerHTML = riskVisual(r);
  else if (validLocation(r))
    disposeMap = mountMap(visual, [r], () => {}, { passive: true });
  else
    visual.innerHTML =
      '<div class="date-visual"><strong>' +
      esc(d.location?.country || "Location not recorded") +
      "</strong><p>Map coordinates unavailable.</p></div>";
}
function issueURL(title, body) {
  const u = new URL(
    "https://github.com/guillearria/global-observatory/issues/new",
  );
  u.searchParams.set("title", title);
  u.searchParams.set("body", body);
  return u.href;
}
function validIssueURL(value) {
  try {
    const u = new URL(value);
    return u.origin === "https://github.com" &&
      /^\/guillearria\/global-observatory\/issues\/[1-9]\d*$/.test(
        u.pathname,
      ) &&
      !u.search &&
      !u.hash
      ? u.href
      : "";
  } catch {
    return "";
  }
}
function about() {
  main.innerHTML = `<article class="about"><h1>A place to observe the world.</h1><p>Explore emergencies, risks and history. Start with the map; follow the sources when you want to go deeper.</p><p>Automated research can be incomplete or wrong. This is a source-linked collection, not an alert service. Response pages lead to organizations’ own response pages; we don’t collect donations or rate charities.</p><section class="source-note"><h2>Sources & freshness</h2><p>Record edit dates are separate from source retrieval dates. Neither guarantees that every figure is current. Missing dates stay missing. Map locations are approximate; death figures and risk labels come from the saved collection.</p></section><h2>Send feedback</h2><p class="small">Suggestions, bugs or corrections. A GitHub account is required. Your issue will be public: don’t include personal or sensitive information.</p><form id="feedback"><label>Type<select id="feedback-type"><option>Suggestion</option><option>Bug</option><option>Data correction</option></select></label><label>Title<input id="feedback-title" required maxlength="100"></label><label>What should change?<textarea id="feedback-body" rows="5" required maxlength="1200"></textarea></label><button type="submit">Prepare GitHub issue</button></form><div id="feedback-result" role="status"></div><details><summary>Track an issue you submitted</summary><p class="small">After submitting on GitHub, copy the issue page URL here. This saves nothing and does not verify the issue.</p><label>Issue URL<input id="issue-url" type="url" placeholder="https://github.com/guillearria/global-observatory/issues/123"></label><button id="track">Show tracking link</button><p id="tracking" role="status"></p></details></article>`;
  document.querySelector("#feedback").onsubmit = (e) => {
    e.preventDefault();
    const rawTitle = document.querySelector("#feedback-title").value.trim(),
      body = document.querySelector("#feedback-body").value.trim();
    if (!rawTitle || !body) {
      document.querySelector("#feedback-result").textContent =
        "Please enter a title and description.";
      return;
    }
    const title = `[${document.querySelector("#feedback-type").value}] ${rawTitle}`,
      url = issueURL(title, body);
    document.querySelector("#feedback-result").innerHTML =
      `<p><strong>Draft prepared. Nothing has been submitted.</strong></p><p>${url.length <= 7000 ? ext(url, "Review and submit on GitHub") : "The draft is too long for a link. Copy the text below into " + ext("https://github.com/guillearria/global-observatory/issues/new", "a new GitHub issue") + "."}</p><p class="small">GitHub will show your tracking URL after you submit.</p><details><summary>Copyable draft</summary><pre>${esc(title + "\n\n" + body)}</pre></details>`;
  };
  document.querySelector("#track").onclick = () => {
    const u = validIssueURL(document.querySelector("#issue-url").value);
    document.querySelector("#tracking").innerHTML = u
      ? ext(u, "Open your issue (user-supplied link, not verified)")
      : "Enter a Global Observatory GitHub issue URL.";
  };
}
let previousRoute = "";
function route() {
  const oldRoute = previousRoute;
  previousRoute = location.hash;
  disposeMap();
  disposeMap = () => {};
  let [kind = "events", raw] = location.hash.slice(1).split("/");
  if (!kind) kind = "events";
  kind = { pulse: "events", history: "historical" }[kind] || kind;
  if (!Object.hasOwn(datasets, kind) && kind !== "about") kind = "events";
  main.className =
    !raw && kind === "historical"
      ? "history-page"
      : kind === "about"
        ? "about-page"
        : "";
  document.querySelectorAll("nav a").forEach((a) => {
    if (a.hash === "#" + kind) a.setAttribute("aria-current", "page");
    else a.removeAttribute("aria-current");
  });
  try {
    if (datasets[kind]?.error) {
      main.innerHTML =
        "<h1>Collection unavailable</h1><p>Please reload or try again later.</p>";
    } else if (kind === "about") about();
    else if (raw) record(kind, decodeURIComponent(raw));
    else if (kind === "events") eventListing();
    else if (kind === "historical") historyView();
    else risks();
  } catch (err) {
    main.innerHTML =
      '<h1>Unable to open this record</h1><a href="#events">Return to emergencies</a>';
    console.error(err);
  }
  main.insertAdjacentHTML("afterbegin", freshness(kind));
  const h = main.querySelector("h1");
  h?.setAttribute("tabindex", "-1");
  h?.focus({ preventScroll: true });
  const [oldKind, oldId] = oldRoute.slice(1).split("/");
  const backLink =
    !raw && oldKind === kind && oldId
      ? [...main.querySelectorAll("h3 a")].find((a) => a.hash === oldRoute)
      : null;
  if (backLink) {
    backLink.focus();
    backLink.scrollIntoView({ block: "center" });
  } else window.scrollTo(0, 0);
  document.title =
    (h?.textContent || "Global Observatory") + " · Global Observatory";
}
// Browser startup
document.querySelector(".skip").onclick = (e) => {
  e.preventDefault();
  main.tabIndex = -1;
  main.focus();
};
loadDatasets().then(() => {
  window.addEventListener("hashchange", route);
  route();
});
