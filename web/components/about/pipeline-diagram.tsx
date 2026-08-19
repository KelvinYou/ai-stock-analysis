import {
  LAYOUT_CONSTANTS as L,
  layoutPipeline,
  type Edge,
  type Pipeline,
  type PipelineNode,
  type Tone,
} from "@/lib/pipeline";
import { cn } from "@/lib/utils";

/**
 * Server-rendered SVG flowchart of the analysis pipeline. Everything is coloured
 * with Tailwind fill-/stroke- utilities so the diagram follows the app's theme
 * tokens (including `.dark`) instead of carrying its own palette.
 *
 * The bull and bear researchers take their direction colours; every other node,
 * every edge and every band stays ink/graphite/rule, so the two arguments are
 * the only thing on the diagram that reads as coloured. Their labels also name
 * them, and the generated <desc> reads the whole graph out, so the hue is never
 * the only way to tell the two apart. SVG cannot take the Tailwind type scale,
 * so the two steps this diagram needs are restated numerically — 11 for labels,
 * 10 for captions, matching micro and mini.
 */

/** The type scale, in the numeric form SVG requires. */
const FS = { label: 11, caption: 10 } as const;

/** Matches the `rounded` token (--radius = 0.25rem) at diagram scale. */
const RX = 4;

/** Mono advance width at `FS.caption`, plus horizontal padding. */
const BADGE_PAD = 14;
const MONO_ADVANCE = 6;

export function PipelineDiagram({ pipeline }: { pipeline: Pipeline }) {
  const { width, height, bands, boxes, edges } = layoutPipeline(pipeline);

  return (
    <figure className="space-y-3">
      <div className="overflow-x-auto rounded-lg border bg-card p-2 sm:p-4">
        <svg
          viewBox={`0 0 ${width} ${height}`}
          role="img"
          aria-labelledby="pipeline-title pipeline-desc"
          className="h-auto w-full min-w-[560px]"
        >
          <title id="pipeline-title">
            Four-layer analysis pipeline, data ingestion through briefing
          </title>
          <desc id="pipeline-desc">{describe(pipeline)}</desc>

          <defs>
            <marker
              id="arrow"
              viewBox="0 0 8 8"
              refX="7"
              refY="4"
              markerWidth="5"
              markerHeight="5"
              orient="auto-start-reverse"
            >
              <path d="M0,0 L8,4 L0,8 z" className="fill-graphite" />
            </marker>
          </defs>

          {bands.map((b, i) => (
            <g key={b.stage.id}>
              <rect
                x={b.x}
                y={b.y}
                width={b.w}
                height={b.h}
                rx={RX}
                className="fill-secondary stroke-rule"
                strokeWidth={1}
              />
              {/* Every band shares one flat fill, so six stages read as one grey
                  column with no rhythm. A left rule stepped by stage index gives
                  each band a distinct identity without adding a new hue. */}
              <rect
                x={b.x}
                y={b.y + RX}
                width={3}
                height={b.h - RX * 2}
                rx={1.5}
                className="fill-graphite"
                style={{ opacity: 0.15 + 0.1 * i }}
              />
              <text
                x={b.x + L.bandPadX}
                y={b.y + 17}
                fontSize={FS.label}
                className="fill-ink font-semibold"
              >
                {b.stage.layer}
                <tspan className="fill-graphite font-normal"> · {b.stage.title}</tspan>
                {b.stage.note && (
                  <tspan className="fill-graphite font-normal"> — {b.stage.note}</tspan>
                )}
              </text>
              {b.stage.model && (
                <ModelBadge
                  x={b.x + b.w - L.bandPadX}
                  y={b.y + 8}
                  model={b.stage.model}
                  modelKey={b.stage.modelKey}
                />
              )}
            </g>
          ))}

          {edges.map((e, i) => (
            <EdgePath key={i} edge={e} />
          ))}

          {boxes.map((box) => (
            <NodeBox key={box.node.id} {...box} />
          ))}

          {/* Labels last: a long edge label can overrun into a box's footprint
              (e.g. the bull/bear exchange), and an opaque box painted after it
              would clip the overrun instead of just the box covering the line. */}
          {edges.map(
            (e, i) => e.label && <EdgeLabel key={`label-${i}`} edge={e} />,
          )}
        </svg>
      </div>
      <figcaption className="text-micro leading-relaxed text-graphite">
        Generated from{" "}
        <code className="num text-mini text-ink">pipeline.json</code> — the
        same file that generates the mermaid diagram in{" "}
        <code className="num text-mini text-ink">architecture.md</code>.
      </figcaption>
    </figure>
  );
}

/**
 * Ground and rule carry the node's role. Only `bull` and `bear` take a hue —
 * they are the one place on this diagram where direction is the content.
 */
const TONE_FILL: Record<Tone, string> = {
  data: "fill-background stroke-rule",
  agent: "fill-background stroke-graphite",
  bull: "fill-card stroke-bull",
  bear: "fill-card stroke-bear",
  output: "fill-secondary stroke-ink",
  muted: "fill-muted stroke-rule",
};

/** Label colour, matched to the stroke so a coloured box is not outlined in one hue and lettered in another. */
const TONE_LABEL: Record<Tone, string> = {
  data: "fill-ink",
  agent: "fill-ink",
  bull: "fill-bull",
  bear: "fill-bear",
  output: "fill-ink",
  muted: "fill-ink",
};

function NodeBox({
  node,
  x,
  y,
  w,
  h,
}: {
  node: PipelineNode;
  x: number;
  y: number;
  w: number;
  h: number;
}) {
  const tone = node.tone ?? "data";
  return (
    <g>
      <rect
        x={x}
        y={y}
        width={w}
        height={h}
        rx={RX}
        strokeWidth={1.5}
        strokeDasharray={node.dashed ? "3 3" : undefined}
        className={cn(TONE_FILL[tone])}
      />
      <text
        x={x + w / 2}
        y={y + L.boxPadY + 10}
        textAnchor="middle"
        fontSize={FS.label}
        className={cn("font-semibold", TONE_LABEL[tone])}
      >
        {node.label}
      </text>
      {node.lines?.map((line, i) => (
        <text
          key={i}
          x={x + w / 2}
          y={y + L.boxPadY + L.titleH + 8 + i * L.lineH}
          textAnchor="middle"
          fontSize={FS.caption}
          className="fill-graphite"
        >
          {line}
        </text>
      ))}
    </g>
  );
}

/** Corner radius for an elbow turn — small enough to stay a flowchart, not a blob. */
const ELBOW_R = 6;

/**
 * Round each interior turn of a polyline into a short quadratic curve instead
 * of a hard corner. A straight 90° elbow reads as a technical schematic;
 * mermaid's default routing rounds these, which is most of the "prettier"
 * gap between this diagram and the mermaid ones elsewhere in the app.
 */
function roundedElbowPath(points: [number, number][]): string {
  if (points.length <= 2) {
    const [[x1, y1], [x2, y2]] = points;
    return `M${x1},${y1} L${x2},${y2}`;
  }
  const parts: string[] = [`M${points[0][0]},${points[0][1]}`];
  for (let i = 1; i < points.length - 1; i++) {
    const [px, py] = points[i - 1];
    const [cx, cy] = points[i];
    const [nx, ny] = points[i + 1];
    const inLen = Math.hypot(cx - px, cy - py);
    const outLen = Math.hypot(nx - cx, ny - cy);
    const r = Math.min(ELBOW_R, inLen / 2, outLen / 2);
    const inX = cx + ((px - cx) / inLen) * r;
    const inY = cy + ((py - cy) / inLen) * r;
    const outX = cx + ((nx - cx) / outLen) * r;
    const outY = cy + ((ny - cy) / outLen) * r;
    parts.push(`L${inX},${inY}`, `Q${cx},${cy} ${outX},${outY}`);
  }
  const last = points[points.length - 1];
  parts.push(`L${last[0]},${last[1]}`);
  return parts.join(" ");
}

function EdgePath({ edge }: { edge: Edge }) {
  const d = roundedElbowPath(edge.points);
  const arrow = edge.arrow || edge.bidirectional ? "url(#arrow)" : undefined;
  return (
    <path
      d={d}
      fill="none"
      strokeWidth={1.5}
      strokeDasharray={edge.dashed ? "3 3" : undefined}
      markerEnd={arrow}
      markerStart={edge.bidirectional ? "url(#arrow)" : undefined}
      className="stroke-graphite"
    />
  );
}

function EdgeLabel({ edge }: { edge: Edge }) {
  const isBus = edge.points.length === 2 && edge.points[0][1] === edge.points[1][1];
  const [mx, my] = midpoint(edge.points);
  return (
    <text
      x={mx}
      y={isBus ? my - 5 : my}
      textAnchor="middle"
      fontSize={FS.caption}
      className="fill-graphite italic"
    >
      {edge.label}
    </text>
  );
}

function ModelBadge({
  x,
  y,
  model,
  modelKey,
}: {
  x: number;
  y: number;
  model: string;
  modelKey?: string;
}) {
  // The label is set in the mono face, so its advance width is predictable —
  // the old estimate was tuned to a proportional face and now overruns.
  const w = BADGE_PAD + model.length * MONO_ADVANCE;
  return (
    <g>
      <title>{modelKey ? `config.py · ${modelKey}` : model}</title>
      <rect
        x={x - w}
        y={y}
        width={w}
        height={14}
        rx={RX}
        className="fill-background stroke-rule"
        strokeWidth={1}
      />
      <text
        x={x - w / 2}
        y={y + 10}
        textAnchor="middle"
        fontSize={FS.caption}
        className="num fill-graphite font-medium"
      >
        {model}
      </text>
    </g>
  );
}

function midpoint(points: [number, number][]): [number, number] {
  const a = points[0];
  const b = points[points.length - 1];
  return [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2];
}

/** Plain-text walkthrough for screen readers — the SVG alone conveys nothing. */
function describe(p: Pipeline): string {
  const stages = p.stages
    .map((s) => {
      const nodes = [...s.rows.flat(), ...(s.sink ? [s.sink] : [])]
        .map((n) => n.label)
        .join(", ");
      return `${s.layer} (${s.title}${s.model ? `, ${s.model}` : ""}): ${nodes}`;
    })
    .join(". ");
  return `${stages}. Output: ${p.output.label}, consumed by ${p.consumers
    .map((c) => c.label)
    .join(", ")}.`;
}
