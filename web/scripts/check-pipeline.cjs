/* Exercise the actual TypeScript layout and React SVG component without a browser. */
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const Module = require("node:module");
const ts = require("typescript");
const { renderToStaticMarkup } = require("react-dom/server");

const root = path.resolve(__dirname, "..");
const loaded = new Map();
function loadSource(filename) {
  if (loaded.has(filename)) return loaded.get(filename).exports;
  const mod = new Module(filename);
  mod.paths = Module._nodeModulePaths(path.dirname(filename));
  loaded.set(filename, mod);
  const nativeRequire = Module.createRequire(filename);
  mod.require = (id) => {
    // The marker guards client bundles; this is a server-side rendering test.
    if (id === "server-only") return {};
    if (id.startsWith("@/")) {
      const stem = path.join(root, id.slice(2));
      const target = [stem + ".ts", stem + ".tsx"].find(fs.existsSync);
      assert(target, `Cannot resolve ${id}`);
      return loadSource(target);
    }
    return nativeRequire(id);
  };
  const source = ts.transpileModule(fs.readFileSync(filename, "utf8"), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020,
      jsx: ts.JsxEmit.ReactJSX, esModuleInterop: true },
  }).outputText;
  mod._compile(source, filename);
  return mod.exports;
}

const { layoutPipeline, validatePipeline } = loadSource(path.join(root, "lib/pipeline.ts"));
const { PipelineDiagram } = loadSource(path.join(root, "components/about/pipeline-diagram.tsx"));
const pipeline = JSON.parse(fs.readFileSync(path.join(root, "../pipeline.json"), "utf8"));
const layout = layoutPipeline(pipeline);
assert.equal(layout.edges.length, pipeline.edges.length);
for (const edge of layout.edges) {
  assert(pipeline.edges.some((e) => e.from === edge.sourceId && e.to === edge.targetId));
  assert(edge.points.every(([x, y]) => Number.isFinite(x) && Number.isFinite(y)
    && x >= 0 && x <= layout.width && y >= 0 && y <= layout.height));
  assert(edge.points.every((p, i) => !i || p[0] !== edge.points[i - 1][0] || p[1] !== edge.points[i - 1][1]));
}
assert(layout.edges.some((e) => e.sourceId === "MEM" && e.targetId === "SYN" && e.dashed));
assert(!layout.edges.some((e) => e.sourceId === "RM" && e.targetId === "MEM"));
for (const [from, to] of [["SYN", "GATE"], ["GATE", "RISK"], ["RISK", "OUT"]]) {
  assert(layout.edges.some((e) => e.sourceId === from && e.targetId === to));
}
for (const corruption of ["endpoint", "duplicate", "kind"]) {
  const bad = structuredClone(pipeline);
  if (corruption === "endpoint") bad.edges[0].to = "MISSING";
  if (corruption === "duplicate") bad.output.id = "MEM";
  if (corruption === "kind") bad.edges[0].kind = "unknown";
  assert.throws(() => validatePipeline(bad));
}
const markup = renderToStaticMarkup(PipelineDiagram({ pipeline }));
assert(markup.includes('data-node-id="GATE"'));
assert(markup.includes('data-edge-from="MEM" data-edge-to="SYN"'));
assert(!markup.includes("NaN"));
const outputIndex = process.argv.indexOf("--svg");
if (outputIndex >= 0) {
  const output = path.resolve(process.argv[outputIndex + 1]);
  const svg = markup.match(/<svg[\s\S]*?<\/svg>/)[0];
  fs.mkdirSync(path.dirname(output), { recursive: true });
  fs.writeFileSync(output, svg);
}
console.log(`Pipeline layout and server-rendered SVG PASS: ${layout.boxes.length} nodes, ${layout.edges.length} canonical edges.`);
