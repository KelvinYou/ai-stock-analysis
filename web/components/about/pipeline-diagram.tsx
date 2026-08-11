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
 */
export function PipelineDiagram({ pipeline }: { pipeline: Pipeline }) {
  const { width, height, bands, boxes, edges } = layoutPipeline(pipeline);

  return (
    <figure className="space-y-3">
      <div className="overflow-x-auto rounded-xl border bg-card p-2 sm:p-4">
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
              <path d="M0,0 L8,4 L0,8 z" className="fill-muted-foreground" />
            </marker>
          </defs>

          {bands.map((b) => (
            <g key={b.stage.id}>
              <rect
                x={b.x}
                y={b.y}
                width={b.w}
                height={b.h}
                rx={10}
                className="fill-muted/40 stroke-border"
                strokeWidth={1}
              />
              <text x={b.x + L.bandPadX} y={b.y + 17} className="fill-foreground text-[11px] font-semibold">
                {b.stage.layer}
                <tspan className="fill-muted-foreground font-normal"> · {b.stage.title}</tspan>
                {b.stage.note && (
                  <tspan className="fill-muted-foreground font-normal"> — {b.stage.note}</tspan>
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
      <figcaption className="text-[11px] leading-relaxed text-muted-foreground">
        Generated from{" "}
        <code className="font-mono text-[10px] text-foreground">pipeline.json</code> — the
        same file that generates the mermaid diagram in{" "}
        <code className="font-mono text-[10px] text-foreground">architecture.md</code>.
      </figcaption>
    </figure>
  );
}

const TONE_FILL: Record<Tone, string> = {
  data: "fill-background stroke-border",
  agent: "fill-background stroke-foreground/25",
  bull: "fill-bull/10 stroke-bull/50",
  bear: "fill-bear/10 stroke-bear/50",
  output: "fill-foreground/[0.06] stroke-foreground/40",
  muted: "fill-muted/60 stroke-border",
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
        rx={7}
        strokeWidth={1}
        strokeDasharray={node.dashed ? "3 3" : undefined}
        className={cn(TONE_FILL[tone])}
      />
      <text
        x={x + w / 2}
        y={y + L.boxPadY + 10}
        textAnchor="middle"
        className={cn(
          "text-[11px] font-semibold",
          tone === "bull"
            ? "fill-bull"
            : tone === "bear"
              ? "fill-bear"
              : "fill-foreground",
        )}
      >
        {node.label}
      </text>
      {node.lines?.map((line, i) => (
        <text
          key={i}
          x={x + w / 2}
          y={y + L.boxPadY + L.titleH + 8 + i * L.lineH}
          textAnchor="middle"
          className="fill-muted-foreground text-[8.5px]"
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
        className="stroke-muted-foreground/50"
      />
      {edge.label && (
        <text
          x={mx}
          y={isBus ? my - 5 : my}
          textAnchor="middle"
          className="fill-muted-foreground text-[8px] italic"
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
  const w = 8 + model.length * 5.6;
  return (
    <g>
      <title>{modelKey ? `config.py · ${modelKey}` : model}</title>
      <rect
        x={x - w}
        y={y}
        width={w}
        height={14}
        rx={7}
        className="fill-background stroke-border"
        strokeWidth={1}
      />
      <text
        x={x - w / 2}
        y={y + 10}
        textAnchor="middle"
        className="fill-muted-foreground text-[8.5px] font-medium"
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
