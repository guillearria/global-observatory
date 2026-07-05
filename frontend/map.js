"use strict";

// World Pulse map: a self-contained equirectangular basemap (NASA Blue Marble, committed
// to the repo) with impact-scaled event markers. No map library, no tile server, no
// external requests — drag to pan, wheel/pinch to zoom, click a marker to jump to its
// card. app.js only touches the two-method GOMap API below, so a richer map (e.g.
// vendored Leaflet) stays a drop-in swap.
(function () {
  const BASE_IMAGE = "./assets/blue-marble-4096.jpg";
  const MIN_ZOOM = 1;
  const MAX_ZOOM = 8;

  const state = {
    container: null,   // #map
    world: null,       // the panned/zoomed basemap element
    tip: null,         // shared tooltip
    zoom: 1,
    panX: 0,
    panY: 0,
    records: [],       // events with finite lat/lon
    markers: [],       // [{el, lat, lon}]
    pointers: new Map(),  // active pointers (drag + pinch)
    pinchDist: 0,
    dragMoved: 0,      // px moved since pointerdown — suppresses click-after-drag
  };

  // Base world width: the smallest 2:1 world that covers the container at zoom 1.
  function baseWidth() {
    const cw = state.container.clientWidth;
    const ch = state.container.clientHeight;
    return Math.max(cw, ch * 2);
  }

  function worldSize() {
    const w = baseWidth() * state.zoom;
    return { w, h: w / 2 };
  }

  // Equirectangular projection into world pixels.
  function project(lat, lon, w, h) {
    return { x: ((lon + 180) / 360) * w, y: ((90 - lat) / 180) * h };
  }

  function clampPan() {
    const cw = state.container.clientWidth;
    const ch = state.container.clientHeight;
    const { w, h } = worldSize();
    state.panX = Math.min(0, Math.max(cw - w, state.panX));
    state.panY = Math.min(0, Math.max(ch - h, state.panY));
  }

  function layout() {
    const { w, h } = worldSize();
    clampPan();
    state.world.style.width = `${w}px`;
    state.world.style.height = `${h}px`;
    state.world.style.transform = `translate(${state.panX}px, ${state.panY}px)`;
    for (const m of state.markers) {
      const p = project(m.lat, m.lon, w, h);
      m.el.style.left = `${p.x}px`;
      m.el.style.top = `${p.y}px`;
    }
  }

  // Zoom keeping the container point (cx, cy) fixed under the cursor/pinch midpoint.
  function zoomAt(cx, cy, factor) {
    const next = Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, state.zoom * factor));
    if (next === state.zoom) return;
    const { w, h } = worldSize();
    const fx = (cx - state.panX) / w;
    const fy = (cy - state.panY) / h;
    state.zoom = next;
    const after = worldSize();
    state.panX = cx - fx * after.w;
    state.panY = cy - fy * after.h;
    hideTip();
    layout();
  }

  function hideTip() {
    if (state.tip) state.tip.hidden = true;
  }

  function showTip(marker, rec) {
    const tip = state.tip;
    tip.replaceChildren();
    const name = document.createElement("strong");
    name.textContent = rec.name || rec.id;
    tip.appendChild(name);
    const summary = ((rec.event || {}).impact || {}).summary || rec.description || "";
    if (summary) {
      const s = document.createElement("span");
      s.textContent = summary.length > 120 ? `${summary.slice(0, 117)}…` : summary;
      tip.appendChild(s);
    }
    tip.hidden = false;
    // Position near the marker, nudged inside the container.
    const cw = state.container.clientWidth;
    const x = parseFloat(marker.style.left) + state.panX;
    const y = parseFloat(marker.style.top) + state.panY;
    tip.style.left = `${Math.max(6, Math.min(cw - tip.offsetWidth - 6, x + 14))}px`;
    tip.style.top = `${Math.max(6, y - tip.offsetHeight - 10)}px`;
  }

  function jumpToCard(rec) {
    const card = document.getElementById(`card-${rec.id}`);
    if (!card) return;
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    // scrollIntoView, never a hash anchor — the URL hash belongs to the tab router.
    card.scrollIntoView({ behavior: reduced ? "auto" : "smooth", block: "start" });
    card.classList.remove("card-flash");
    void card.offsetWidth; // restart the animation if the same card is clicked twice
    card.classList.add("card-flash");
  }

  function markerFor(rec) {
    const rank = (rec.sort_keys && rec.sort_keys.impact_rank) || 1;
    const size = 8 + 4 * Math.min(4, Math.max(1, rank));
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = `map-marker r${Math.min(4, Math.max(1, rank))}`;
    btn.style.width = `${size}px`;
    btn.style.height = `${size}px`;
    btn.setAttribute("aria-label", `${rec.name || rec.id} — show event card`);
    btn.addEventListener("mouseenter", () => showTip(btn, rec));
    btn.addEventListener("mouseleave", hideTip);
    btn.addEventListener("focus", () => showTip(btn, rec));
    btn.addEventListener("blur", hideTip);
    btn.addEventListener("click", (e) => {
      if (state.dragMoved > 6) return; // a drag that ended on the marker, not a click
      e.preventDefault();
      hideTip();
      jumpToCard(rec);
    });
    return btn;
  }

  function onPointerDown(e) {
    // No pointer capture yet: capturing here would retarget the eventual click away
    // from the marker buttons. onPointerMove captures once a real drag starts.
    state.pointers.set(e.pointerId, { x: e.clientX, y: e.clientY });
    state.dragMoved = 0;
    if (state.pointers.size === 2) {
      const [a, b] = [...state.pointers.values()];
      state.pinchDist = Math.hypot(a.x - b.x, a.y - b.y);
    }
    state.container.classList.add("dragging");
  }

  function onPointerMove(e) {
    const prev = state.pointers.get(e.pointerId);
    if (!prev) return;
    const cur = { x: e.clientX, y: e.clientY };
    state.pointers.set(e.pointerId, cur);

    if (state.pointers.size === 2) {
      // Pinch: zoom about the midpoint by the distance ratio.
      const [a, b] = [...state.pointers.values()];
      const dist = Math.hypot(a.x - b.x, a.y - b.y);
      if (state.pinchDist > 0) {
        const rect = state.container.getBoundingClientRect();
        const mx = (a.x + b.x) / 2 - rect.left;
        const my = (a.y + b.y) / 2 - rect.top;
        zoomAt(mx, my, dist / state.pinchDist);
      }
      state.pinchDist = dist;
      state.dragMoved = 100; // a pinch is never a click
      return;
    }

    const dx = cur.x - prev.x;
    const dy = cur.y - prev.y;
    state.dragMoved += Math.abs(dx) + Math.abs(dy);
    if (state.dragMoved > 4 && !state.container.hasPointerCapture(e.pointerId)) {
      state.container.setPointerCapture(e.pointerId); // keep the drag when leaving the map
      hideTip();
    }
    state.panX += dx;
    state.panY += dy;
    layout();
  }

  function onPointerEnd(e) {
    state.pointers.delete(e.pointerId);
    state.pinchDist = 0;
    if (!state.pointers.size) state.container.classList.remove("dragging");
  }

  function onWheel(e) {
    e.preventDefault(); // the map owns scroll inside itself; the page keeps its own
    const rect = state.container.getBoundingClientRect();
    const factor = Math.exp(-e.deltaY * 0.0015);
    zoomAt(e.clientX - rect.left, e.clientY - rect.top, factor);
  }

  function onDblClick(e) {
    const rect = state.container.getBoundingClientRect();
    zoomAt(e.clientX - rect.left, e.clientY - rect.top, 1.6);
  }

  function init() {
    if (state.container) return true;
    const container = document.getElementById("map");
    if (!container) return false;
    state.container = container;

    state.world = document.createElement("div");
    state.world.className = "map-world";
    const img = document.createElement("img");
    img.src = BASE_IMAGE;
    img.alt = ""; // decorative; the marker buttons carry the semantics
    state.world.appendChild(img);
    container.appendChild(state.world);

    state.tip = document.createElement("div");
    state.tip.className = "map-tip";
    state.tip.hidden = true;
    container.appendChild(state.tip);

    container.addEventListener("pointerdown", onPointerDown);
    container.addEventListener("pointermove", onPointerMove);
    container.addEventListener("pointerup", onPointerEnd);
    container.addEventListener("pointercancel", onPointerEnd);
    container.addEventListener("wheel", onWheel, { passive: false });
    container.addEventListener("dblclick", onDblClick);
    window.addEventListener("resize", invalidate);

    // First view: whole world, centered.
    const cw = container.clientWidth;
    const ch = container.clientHeight;
    const { w, h } = worldSize();
    state.panX = (cw - w) / 2;
    state.panY = (ch - h) / 2;
    return true;
  }

  // Re-render markers from the latest events payload. Called by app.js on every
  // events.json paint, so a daily data refresh updates the map with no extra plumbing.
  function setEvents(records) {
    const section = document.getElementById("map-section");
    if (!section) return;
    state.records = (records || []).filter((r) => {
      const loc = (r.event || {}).location || {};
      return Number.isFinite(loc.lat) && Number.isFinite(loc.lon);
    });
    if (!state.records.length) {
      section.hidden = true; // nothing locatable -> no empty map
      return;
    }
    if (!init()) return;
    section.hidden = false;

    for (const m of state.markers) m.el.remove();
    state.markers = state.records.map((rec) => {
      const loc = rec.event.location;
      const el = markerFor(rec);
      state.world.appendChild(el);
      return { el, lat: loc.lat, lon: loc.lon };
    });
    invalidate();
  }

  // Re-measure and re-clamp — needed after a resize or when the pulse tab becomes
  // visible again (an element laid out while hidden has zero size).
  function invalidate() {
    if (!state.container || !state.records.length) return;
    if (!state.container.clientWidth) return; // still hidden; showTab will call again
    hideTip();
    layout();
  }

  window.GOMap = { setEvents, invalidate };
})();
