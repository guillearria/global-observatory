const fs = require("node:fs"),
  vm = require("node:vm"),
  assert = require("node:assert/strict"),
  { test } = require("node:test");
const code = fs
  .readFileSync(
    require("node:path").join(__dirname, "../frontend/app.js"),
    "utf8",
  )
  .split("// Browser startup")[0];
const ctx = vm.createContext({
  URL,
  console: { error() {} },
  document: {
    getElementById: () => ({ textContent: "{}" }),
    querySelector: () => ({}),
  },
});
vm.runInContext(
  code +
    "\nglobalThis.api={esc,safe,date,sources,helpFor,helpPages,bucket,year,toStoredYear,endYear,yearMatch,historicalOrder,validLocation,issueURL,validIssueURL,historyBounds,freshness,loadDatasets,recordUpdates,recordFacts};",
  ctx,
);
const a = ctx.api;
test("date validation preserves unknown and never retrieved", () => {
  for (const x of [null, undefined, "undefined", "2026-02-30", "0000-01-01"])
    assert.equal(a.date(x), "");
  assert.equal(a.date("2024-02-29"), "2024-02-29");
  assert.match(
    a.sources({ claims: [{ retrieved_date: null }] }),
    /not recorded/,
  );
  assert.match(
    a.sources({ claims: [{ retrieved_date: "" }] }),
    /never retrieved/,
  );
});
test("death marker semantics distinguish unknown and zero; reject numeric strings", () => {
  for (const n of [null, undefined, NaN, -1, "30"])
    assert.equal(a.bucket(n), "unknown");
  for (const [n, v] of [
    [0, "zero"],
    [1, "small"],
    [99, "small"],
    [100, "medium"],
    [999, "medium"],
    [1000, "large"],
  ])
    assert.equal(a.bucket(n), v);
});
test("affected people in prose are not rendered as recorded displacement", () => {
  const r = {
    event: {
      impact: {
        deaths: 335,
        displaced: null,
        summary: "486,917 people affected; displacement is unknown.",
      },
    },
  };
  assert.match(a.recordFacts(r), /Recorded deaths: 335/);
  assert.doesNotMatch(a.recordFacts(r), /Recorded displaced|486,917/);
  assert.match(r.event.impact.summary, /486,917 people affected/);
  r.event.impact.displaced = 0;
  assert.match(a.recordFacts(r), /Recorded displaced: 0/);
  r.event.impact.displaced = 123;
  assert.match(a.recordFacts(r), /Recorded displaced: 123/);
});
test("map rejects missing and out of range coordinates; accepts real zero", () => {
  assert.equal(
    !!a.validLocation({ event: { location: { lat: 0, lon: 0 } } }),
    true,
  );
  for (const l of [
    { lat: null, lon: 2 },
    { lat: 95, lon: 0 },
    { lat: 0, lon: 181 },
  ])
    assert.equal(!!a.validLocation({ event: { location: l } }), false);
});
test("history overlaps recorded ranges; unknown end matches only start", () => {
  const r = (s, e) => ({ historical: { year_start: s, year_end: e } });
  assert.equal(a.yearMatch(r(-1, 1), 1, 1), true);
  assert.equal(a.yearMatch(r(-1, null), 1, 10), false);
  assert.equal(a.yearMatch(r(1981, null), 2000, 2026), false);
  assert.equal(a.yearMatch(r(1400, 1500), 1450, 1460), true);
  assert.equal(a.year(0), "1 BCE");
  assert.equal(a.year(-1), "2 BCE");
  assert.equal(a.toStoredYear(-1), 0);
  assert.equal(a.toStoredYear(-2200), -2199);
  assert.equal(a.year(1), "1 CE");
  assert.equal(
    a.historicalOrder(
      { id: "b", historical: { year_start: 10 } },
      { id: "a", historical: { year_start: 10 } },
    ),
    1,
  );
});
test("help is explicitly event scoped; no epidemic donation inference", () => {
  assert.equal(a.helpFor("sudan-displacement-crisis").length, 1);
  assert.equal(a.helpFor("sudan-cholera-outbreak-2026").length, 0);
  assert.equal(a.helpFor("ebola-bundibugyo-drc-2026").length, 0);
  for (const p of a.helpPages) assert.match(p.url, /^https:\/\//);
});
test("feedback only prepares correctly encoded public issue URL", () => {
  const u = new URL(a.issueURL("Test & <script>", "A?\nB#C"));
  assert.equal(u.origin, "https://github.com");
  assert.equal(u.searchParams.get("body"), "A?\nB#C");
  assert.equal(
    a.validIssueURL(
      "https://github.com/guillearria/global-observatory/issues/123",
    ),
    "https://github.com/guillearria/global-observatory/issues/123",
  );
  for (const s of [
    "https://github.com.evil/x",
    "https://github.com/other/repo/issues/1",
    "javascript:alert(1)",
    "https://github.com/guillearria/global-observatory/issues/0",
  ])
    assert.equal(a.validIssueURL(s), "");
});
test("unsafe links and text are escaped", () => {
  assert.equal(a.safe("javascript:alert(1)"), "");
  assert.equal(a.esc("<img>"), "&lt;img&gt;");
});

test("explicit ongoing end differs from missing end", () => {
  assert.equal(
    a.endYear({ year_end: null, date_display: "1981–present" }),
    new Date().getUTCFullYear(),
  );
  assert.equal(
    a.yearMatch(
      {
        historical: {
          year_start: 1981,
          year_end: null,
          date_display: "1981–present",
        },
      },
      2020,
      2026,
    ),
    true,
  );
});
test("reviewed help mappings have explicit IDs; missing records warn without blocking refreshes", () => {
  const data = JSON.parse(
    fs.readFileSync(
      require("node:path").join(__dirname, "../frontend/data/events.json"),
    ),
  );
  const ids = new Set(data.published.map((r) => r.id));
  for (const p of a.helpPages)
    for (const id of p.ids) {
      assert.match(id, /^[a-z0-9-]+$/);
      if (!ids.has(id)) console.warn(`Response mapping needs review: ${id}`);
    }
});
test("all historical records fit derived bounds; BCE conversion agrees with known records", () => {
  const data = JSON.parse(
    fs.readFileSync(
      require("node:path").join(__dirname, "../frontend/data/historical.json"),
    ),
  );
  assert.ok(data.published.length > 0);
  const bounds = a.historyBounds(data.published);
  for (const r of data.published) {
    assert.equal(Number.isInteger(r.historical.year_start), true);
    assert.equal(a.yearMatch(r, a.toStoredYear(bounds.min), bounds.max), true);
  }
  assert.equal(
    a.year(
      data.published.find((r) => r.id === "fall-of-ur").historical.year_start,
    ),
    "2004 BCE",
  );
});
vm.runInContext(
  "mountMap=()=>()=>{};api.renderRecord=r=>{datasets.events={published:[r]};record('events',r.id);return main.innerHTML};api.normalizedText=normalizedText;",
  ctx,
);
test("all published event descriptions render complete without duplicate overview disclosure", () => {
  const rows = JSON.parse(
    fs.readFileSync(
      require("node:path").join(__dirname, "../frontend/data/events.json"),
    ),
  ).published;
  for (const r of rows) {
    const html = a.renderRecord(r);
    assert.ok(
      html.includes(
        "<p>" + a.esc(r.description || r.event.summary || "") + "</p></div>",
      ),
      r.id,
    );
    assert.doesNotMatch(html, /<summary>Full context|<h2>At a glance/);
    assert.match(html, /<details><summary>Evidence/);
  }
});
test("duplicate context comparison ignores whitespace and case but preserves additions", () => {
  assert.equal(
    a.normalizedText("  Full\n  TEXT "),
    a.normalizedText("full text"),
  );
  assert.notEqual(
    a.normalizedText("full text plus detail"),
    a.normalizedText("full text"),
  );
});

test("production loader reads current relative aggregates without cache or embedded snapshots", async () => {
  const calls = [];
  await a.loadDatasets(async (url, options) => {
    calls.push([url, options.cache]);
    return {
      ok: true,
      json: async () => ({
        last_updated: "2026-11-04T09:00:00Z",
        published: [],
        under_review: [{ id: "quarantined" }],
      }),
    };
  });
  assert.equal(calls.length, 3);
  for (const [url, cache] of calls) {
    assert.match(url, /^\.\/data\/(events|threats|historical)\.json$/);
    assert.equal(cache, "no-cache");
  }
  assert.equal(a.freshness("events", Date.parse("2026-11-05T09:00:00Z")), "");
  assert.match(
    a.freshness("events", Date.parse("2026-11-07T09:00:00Z")),
    /not been refreshed/,
  );
  assert.equal(a.freshness("historical", Date.parse("2099-01-01")), "");
  await a.loadDatasets(async () => ({ ok: false, status: 503 }));
  assert.match(a.freshness("events"), /unavailable or invalid/);
});
test("history expands to incoming ancient and later records", () => {
  const bounds = a.historyBounds([
    { historical: { year_start: -5000, year_end: 2100 } },
  ]);
  assert.equal(bounds.min, -5001);
  assert.equal(bounds.max, 2100);
});
test("detail keeps original source, update history and retrieval notes", () => {
  const r = {
    event: {
      live_source_url: "https://example.org/live",
      impact: { deaths: 0 },
    },
    claims: [
      {
        retrieved_date: null,
        retrieval_note: "Date not recorded in original import.",
      },
    ],
    updates: [{ date: "2026-11-04", text: "A material update <safe>" }],
  };
  assert.match(a.recordFacts(r), /Latest at source/);
  assert.match(a.recordFacts(r), /Recorded deaths: 0/);
  assert.doesNotMatch(a.recordFacts(r), /Latest dated source retrieval/);
  assert.match(a.recordUpdates(r), /material update &lt;safe&gt;/);
  assert.match(a.sources(r), /Date not recorded in original import/);
});
