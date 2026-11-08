const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const crypto = require("node:crypto");
const ts = require("typescript");
const root = path.resolve(__dirname, "..");
function compiled(file, imports = {}, extra = {}) {
  const exportsObject = {};
  const source = ts.transpileModule(fs.readFileSync(path.join(root, file), "utf8"), {
    compilerOptions: {module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022},
  }).outputText;
  vm.runInNewContext(source, {exports: exportsObject, require: name => name in imports ? imports[name] : require(name), URL, ...extra});
  return exportsObject;
}
const allocation = compiled("lib/allocation-types.ts");
const types = compiled("lib/momentum-types.ts", {"./allocation-types": allocation});
const raw = fs.readFileSync(path.join(root,"data/momentum.json"), "utf8");
const hash = fs.readFileSync(path.join(root,"data/momentum.sha256"), "utf8").trim();
assert.equal(crypto.createHash("sha256").update(raw).digest("hex"), hash);
const data = JSON.parse(raw);
assert(types.isMomentumDashboard(data));
const legacy = structuredClone(data); delete legacy.price_evidence;
assert(types.isMomentumDashboard(legacy), "Legacy snapshots remain readable without invented provenance");
const withEvidence = structuredClone(data);
withEvidence.price_evidence = {
  primary_source: {name: "Primary", url: "https://example.com/"},
  supplemental_source: {name: "Secondary", url: "https://example.org/"},
  missing_sessions: [{date: data.preview.as_of, tickers: [data.strategy.universe[0]]}],
  supplemented_sessions: [{date: data.preview.as_of, tickers: [data.strategy.universe[0]]}],
};
assert(types.isMomentumDashboard(withEvidence));
for (const corrupt of [
  e => {e.supplemental_source = null;},
  e => {e.primary_source.url = "javascript:alert(1)";},
  e => {e.missing_sessions[0].tickers = ["OTHER"];},
  e => {e.supplemented_sessions[0].date = "2000-01-01";},
  e => {e.missing_sessions[0].date = "2026-02-30";},
  e => {e.private_balance = 123;},
]) {
  const bad = structuredClone(withEvidence); corrupt(bad.price_evidence);
  assert.equal(types.isMomentumDashboard(bad), false);
}
assert.equal(data.context.status, "available");
assert.equal(data.context.stocks.length, data.strategy.universe.length);
for (const corrupt of [
  d => {d.context.stocks[0].close = NaN;},
  d => {d.context.stocks[0].drawdown_63 = 0.1;},
  d => {d.context.stocks.pop();},
  d => {d.context.stocks[0].returns.m1 = "0.2";},
  d => {d.context.periods.m3.start = "2026-02-30";},
  d => {d.context.periods.m3.end = "2000-01-01";},
  d => {d.context.market.curve[0].market = NaN;},
  d => {d.context.cycle.start = d.context.cycle.decision_date;},
  d => {d.context.cycle.rows[0].net_scenario = 10;},
  d => {d.context.ranking_history[0].ranking[0].ticker = "OTHER";},
]) {
  const bad = structuredClone(data); corrupt(bad);
  assert.equal(types.isMomentumDashboard(bad), false);
}
const oldContext = structuredClone(data); delete oldContext.context; delete oldContext.reference_evidence;
assert(types.isMomentumDashboard(oldContext), "Existing v1 snapshots remain readable");
const recapturedOlderSession = structuredClone(data);
recapturedOlderSession.generated_at_utc = new Date(Date.parse(data.generated_at_utc)+1000).toISOString();
recapturedOlderSession.preview.as_of = "2000-01-01";
assert.equal(types.shouldReplaceMomentumSnapshot(data, recapturedOlderSession), false, "A new capture clock must not regress the price session");
const olderCapture = structuredClone(data); olderCapture.generated_at_utc = new Date(Date.parse(data.generated_at_utc)-1000).toISOString();
assert.equal(types.shouldReplaceMomentumSnapshot(data, olderCapture), false);
assert.equal(types.shouldReplaceMomentumSnapshot(data, data), true);
// Frozen NYSE schedule fixture: independent of the daily artifact's capture date.
const calendarFixture=structuredClone(data);
calendarFixture.session_calendar={exchange:"XNYS",library:"Frozen NYSE fixture",source_url:"https://www.nyse.com/trade/hours-calendars",valid_from_utc:"2026-10-01T00:00:00Z",valid_until_utc:"2026-12-01T00:00:00Z",sessions:[
 {date:"2026-10-29",close_utc:"2026-10-29T20:00:00Z"},{date:"2026-10-30",close_utc:"2026-10-30T20:00:00Z"},
 {date:"2026-11-05",close_utc:"2026-11-05T21:00:00Z"},{date:"2026-11-06",close_utc:"2026-11-06T21:00:00Z"},
 {date:"2026-11-25",close_utc:"2026-11-25T21:00:00Z"},{date:"2026-11-27",close_utc:"2026-11-27T18:00:00Z"},
]};
const syntheticSession = session => {const d=structuredClone(calendarFixture);d.data_sessions.stocks_date=session;d.data_sessions.references.forEach(r=>{r.date=session;r.complete=true;});return d;};
assert.equal(types.momentumFreshness(syntheticSession("2026-11-05"),new Date("2026-11-06T02:00:00Z")).status,"latest");
const clockOnly=syntheticSession("2026-11-05");clockOnly.cycle_month="2026-11";clockOnly.generated_at_utc="2026-11-06T21:00:00Z";
assert.equal(types.momentumFreshness(clockOnly,new Date("2026-11-06T21:00:00Z")).expected_session,"2026-11-06");
assert.equal(types.momentumDashboardForDate(clockOnly,new Date("2026-11-06T21:00:00Z")).monthly.status,"unavailable", "Fresh capture of yesterday's prices is still delayed");
for(const [clock,session] of [
 ["2026-10-30T19:59:59Z","2026-10-29"],["2026-10-30T20:00:00Z","2026-10-30"],
 ["2026-11-06T20:59:59Z","2026-11-05"],["2026-11-08T12:00:00Z","2026-11-06"],
 ["2026-11-26T22:00:00Z","2026-11-25"],["2026-11-27T17:59:59Z","2026-11-25"],
 ["2026-11-27T18:00:00Z","2026-11-27"],
]){const fixture=syntheticSession(session);fixture.cycle_month=clock.slice(0,7);assert.equal(types.momentumFreshness(fixture,new Date(clock)).status,"latest",clock);}
const partial=structuredClone(data);partial.data_sessions.references.at(-1).complete=false;
assert.equal(types.momentumFreshness(partial,new Date(data.generated_at_utc)).status,"partial");
const unverified=structuredClone(data);delete unverified.session_calendar;
assert.equal(types.momentumDashboardForDate(unverified,new Date(data.generated_at_utc)).monthly.status,"unavailable");
assert.equal(types.momentumFreshness(data,new Date(data.session_calendar.valid_until_utc)).status,"unverified");
for (const corrupt of [
 d=>{d.session_calendar.sessions[0].close_utc="not-a-time";},
 d=>{d.data_sessions.references.pop();},
 d=>{d.context.comparisons[0].curve[0].value=NaN;},
]) {const bad=structuredClone(data);corrupt(bad);assert.equal(types.isMomentumDashboard(bad),false);}
assert.equal(data.context.momentum_curve.status,"available");
assert.equal(data.context.momentum_curve.curve.length,data.context.market.curve.length);
assert.equal(data.context.momentum_curve.curve[0].date,data.context.market.curve[0].date);
for(const corrupt of [
 d=>{d.context.momentum_curve.curve[0].value=101;},
 d=>{d.context.momentum_curve.curve.at(-1).value=NaN;},
 d=>{d.context.momentum_curve.rebalances[0].execution_date=d.context.momentum_curve.rebalances[0].decision_date;},
 d=>{d.context.momentum_curve.cost_bps_per_side=20;},
 d=>{d.context.momentum_curve.rebalances[0].tickers=["AAA","AAA","AAA"];},
]){const bad=structuredClone(data);corrupt(bad);assert.equal(types.isMomentumDashboard(bad),false);}
const now = new Date(data.generated_at_utc);
assert.equal(types.momentumDashboardForDate(data, now).preview.status, "available");
assert.equal(types.momentumDashboardForDate(data, new Date(now.getTime()+7*86400000)).monthly.status,"unavailable");
for (const corrupt of [
  d => {d.ai_required = true;}, d => {d.promotion_ready = true;},
  d => {d.preview.ranking.pop();}, d => {d.monthly.ranking[0].target_weight = 1;},
  d => {d.monthly.as_of = d.preview.as_of;},
  d => {d.strategy.universe.push("OTHER");}, d => {d.preview.ranking[0].score = NaN;},
]) {
  const bad = structuredClone(data); corrupt(bad); assert.equal(types.isMomentumDashboard(bad),false);
}
(async () => {
  let calls = 0;
  const source = compiled("lib/momentum-data.ts", {"server-only": {}, "./momentum-types": types}, {
    process: {env: {NODE_ENV: "production", MOMENTUM_SNAPSHOT_URL: "https://example.invalid/momentum.json"}},
    URL, AbortSignal,
    fetch: async address => {calls++; return {ok:true,text: async () => address.endsWith(".json") ? raw : hash};},
  });
  assert((await source.loadMomentumDashboard()).data);
  assert.equal(calls,2);
  const corruptSource = compiled("lib/momentum-data.ts", {"server-only": {}, "./momentum-types": types}, {
    process: {env: {NODE_ENV: "production", MOMENTUM_SNAPSHOT_URL: "https://example.invalid/momentum.json"}},
    URL, AbortSignal, fetch: async () => ({ok:true,text: async () => raw}),
  });
  assert.equal((await corruptSource.loadMomentumDashboard()).data,null);
  const successRoute = compiled("app/api/momentum/route.ts", {"@/lib/momentum-data": {loadMomentumDashboard: async () => ({data, error:null})}}, {Response});
  const response = await successRoute.GET();
  assert.equal(response.status, 200); assert.equal(response.headers.get("Cache-Control"), "no-store");
  const failedRoute = compiled("app/api/momentum/route.ts", {"@/lib/momentum-data": {loadMomentumDashboard: async () => ({data:null, error:"Unverified snapshot"})}}, {Response});
  assert.equal((await failedRoute.GET()).status, 503);
  console.log("Momentum contract PASS: monthly/daily separation, stale suppression, source verification and no AI dependency.");
})().catch(error => {console.error(error);process.exit(1);});
