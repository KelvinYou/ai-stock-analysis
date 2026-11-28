/* Check the exported Python -> JSON -> TypeScript display boundary. */
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const crypto = require("node:crypto");
const ts = require("typescript");
const root = path.resolve(__dirname, "..");
const exportsObject = {};
const source = ts.transpileModule(fs.readFileSync(path.join(root, "lib/allocation-types.ts"), "utf8"), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
}).outputText;
vm.runInNewContext(source, { exports: exportsObject });
const { isAllocationResearch, isCurrentMomentum, currentMomentumForDate, isCurrentRanking, currentRankingForDate } = exportsObject;
const bytes = fs.readFileSync(path.join(root, "data/allocation-research.json"));
const hash = fs.readFileSync(path.join(root, "data/allocation-research.sha256"), "utf8").trim();
assert.equal(crypto.createHash("sha256").update(bytes).digest("hex"), hash);
const data = JSON.parse(bytes);
assert(isAllocationResearch(data));
const legacy = structuredClone(data);
delete legacy.current_momentum;
assert(isAllocationResearch(legacy));
assert.equal(currentMomentumForDate(undefined).status, "unavailable");
const snapshot = {
  status: "available", scope: "indicative_price_only", as_of: "2026-10-26",
  captured_at_utc: "2026-10-27T03:00:00+00:00", source_sha256: "a".repeat(64),
  lookback_months: 12, top_n: 3, universe: ["AAA", "BBB", "CCC", "DDD"],
  ranking: ["AAA", "BBB", "CCC", "DDD"].map((ticker,i) => ({
    ticker, score: [0.4,0.3,0.2,0.1][i], lookback_date: "2025-10-24", target_weight: i < 3 ? 1/3 : 0,
  })),
};
assert(isCurrentMomentum(snapshot));
assert.equal(currentMomentumForDate(snapshot, new Date("2026-10-27T04:00:00Z")).status, "available");
assert.equal(currentMomentumForDate(snapshot, new Date("2026-10-31T04:00:00Z")).status, "unavailable");
assert.equal(currentMomentumForDate(snapshot, new Date("2026-10-26T04:00:00Z")).status, "unavailable");
for (const corrupt of [
  s => { s.ranking.pop(); }, s => { s.ranking.reverse(); },
  s => { s.ranking[0].score = NaN; }, s => { s.ranking[0].target_weight = 1; },
  s => { s.ranking[1].ticker = "AAA"; }, s => { s.scope = "buy_recommendation"; },
  s => { s.captured_at_utc = "2026-10-27T03:00:00"; },
]) {
  const bad = structuredClone(snapshot); corrupt(bad); assert.equal(isCurrentMomentum(bad), false);
}
if (data.current_momentum?.status === "available") {
  const bad = structuredClone(data); bad.current_momentum.universe[0] = "OTHER";
  assert.equal(isAllocationResearch(bad), false);
}
const monthly = data.experiments.find(e => e.kind === "monthly");
const episodes = data.experiments.find(e => e.kind === "episodes");
assert.equal(monthly.arms.find(a => a.id === "ai_only").net_return, null);
assert.equal(episodes.arms.find(a => a.id === "ai_only").net_return, 0);
assert.equal(episodes.arms.find(a => a.id === "ai_only").mean_exposure, 0);
for (const corrupt of [
  d => { d.version = 2; },
  d => { d.default_id = "absent"; },
  d => { d.experiments[0].id = 'bad"\r\nheader'; },
  d => { d.experiments[0].curve.pop(); },
  d => { d.experiments[0].curve[0].allocator = NaN; },
  d => { d.experiments[0].ci.reverse(); },
  d => { d.experiments[0].arms[2].net_return = 0; },
  d => { d.experiments[0].arms.push(d.experiments[0].arms[0]); },
  d => { d.experiments[0].arms[0].mean_exposure = 2; },
]) {
  const bad = structuredClone(data);
  corrupt(bad);
  assert.equal(isAllocationResearch(bad), false);
}
console.log(`Allocation display contract PASS: ${data.experiments.length} verified experiments, absent and zero AI remain distinct.`);

// Current ranking: contract, expiry and corruption must fail closed.
const ranking = data.current_ranking;
assert(ranking && isCurrentRanking(ranking));
if (ranking.status === "available") {
  const asOf = new Date(`${ranking.as_of}T04:00:00Z`);
  const next = new Date(asOf.getTime() + 86_400_000);
  assert.equal(currentRankingForDate(ranking, next).status, "available");
  assert.equal(currentRankingForDate(ranking, new Date(asOf.getTime() + 6 * 86_400_000)).status, "unavailable");
  assert.equal(currentRankingForDate(ranking, asOf).status, "unavailable");
  for (const corrupt of [
    c => { const r = Object.values(c.experiments)[0].rules[0]; r.ranking[0].weight += 0.2; },
    c => { const r = Object.values(c.experiments)[0].rules[0]; r.ranking[1].rank = 9; },
    c => { const r = Object.values(c.experiments)[0].rules[0]; r.ranking.pop(); },
    c => { const r = Object.values(c.experiments)[0].rules[0]; r.ranking[0].value = NaN; },
    c => { const t = Object.keys(c.series)[0]; c.series[t].close.pop(); },
    c => { c.scope = "buy_recommendation"; },
    c => { c.captured_at_utc = "2026-11-11T03:00:00"; },
    c => { const r = Object.values(c.experiments)[0].rules[0]; r.history.at(-1).selected = []; },
    c => { const r = Object.values(c.experiments)[0].rules[0]; r.history[0].selected = ["NOPE"]; },
    c => { const r = Object.values(c.experiments)[0].rules[0]; r.history.reverse(); },
  ]) {
    const bad = structuredClone(ranking);
    corrupt(bad);
    assert(!isCurrentRanking(bad));
  }
}
assert.equal(currentRankingForDate(undefined).status, "unavailable");
console.log("Current ranking contract PASS");
