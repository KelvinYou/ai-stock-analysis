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
const { isAllocationResearch } = exportsObject;
const bytes = fs.readFileSync(path.join(root, "data/allocation-research.json"));
const hash = fs.readFileSync(path.join(root, "data/allocation-research.sha256"), "utf8").trim();
assert.equal(crypto.createHash("sha256").update(bytes).digest("hex"), hash);
const data = JSON.parse(bytes);
assert(isAllocationResearch(data));
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
