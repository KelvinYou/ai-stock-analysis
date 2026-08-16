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

          {bands.map((b) => (
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
        strokeWidth={1}
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

function EdgePath({ edge }: { edge: Edge }) {
  const d = edge.points
    .map(([px, py], i) => `${i === 0 ? "M" : "L"}${px},${py}`)
    .join(" ");
  const isBus = edge.points.length === 2 && edge.points[0][1] === edge.points[1][1];
  const arrow = edge.arrow || edge.bidirectional ? "url(#arrow)" : undefined;

  // Label the midpoint of the segment; nudge horizontal edges above the line.
  const [mx, my] = midpoint(edge.points);
  return (
    <g>
      <path
        d={d}
        fill="none"
        strokeWidth={1}
        strokeDasharray={edge.dashed ? "3 3" : undefined}
        markerEnd={arrow}
        markerStart={edge.bidirectional ? "url(#arrow)" : undefined}
        className="stroke-graphite"
      />
      {edge.label && (
        <text
          x={mx}
          y={isBus ? my - 5 : my}
          textAnchor="middle"
          fontSize={FS.caption}
          className="fill-graphite italic"
        >
          {edge.label}
        </text>
      )}
    </g>
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
