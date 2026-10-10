import "server-only";

import { promises as fs } from "node:fs";
import path from "node:path";
import { cache } from "react";

/**
 * The pipeline diagram is generated from ../pipeline.json — the same file
 * scripts/sync_architecture.py turns into the mermaid block in architecture.md.
 * Layout is computed here (pure functions) so adding an agent to a layer
 * repositions everything automatically instead of needing hand-tuned coordinates.
 */

export type Tone = "data" | "agent" | "bull" | "bear" | "output" | "muted";

export interface PipelineNode {
  id: string;
  label: string;
  lines?: string[];
  tone?: Tone;
  dashed?: boolean;
  /** Caption drawn on the edges leaving this node. */
  edgeLabel?: string;
}

export interface PipelineStage {
  id: string;
  layer: string;
  title: string;
  note?: string;
  model?: string;
  modelKey?: string;
  /** Boxes laid out top-to-bottom; each row is a horizontal band of boxes. */
  rows: PipelineNode[][];
  /** Optional single box the rows converge into (e.g. DataStore). */
  sink?: PipelineNode;
  /** When a row holds exactly two boxes, label the double-headed arrow between them. */
  pairLabel?: string;
}

export interface Pipeline {
  stages: PipelineStage[];
  output: PipelineNode;
  consumers: PipelineNode[];
  /** Explicit dependencies take precedence over legacy row chaining. */
  edges?: PipelineConnection[];
}

export interface PipelineConnection {
  from: string;
  to: string;
  kind: "flow" | "conditional" | "bidirectional";
  label?: string;
}

const PIPELINE_FILE = process.env.STOCK_PIPELINE_FILE
  ? path.resolve(process.env.STOCK_PIPELINE_FILE)
  : path.resolve(process.cwd(), "..", "pipeline.json");

export const loadPipeline = cache(async (): Promise<Pipeline | null> => {
  try {
    const raw = await fs.readFile(PIPELINE_FILE, "utf8");
    const parsed = JSON.parse(raw) as Pipeline;
    validatePipeline(parsed);
    return parsed;
  } catch {
    return null;
  }
});

export function validatePipeline(pipeline: Pipeline): void {
  if (!pipeline.stages?.length || !pipeline.output || !Array.isArray(pipeline.consumers)) {
    throw new Error("Invalid pipeline structure");
  }
  const nodes = pipeline.stages.flatMap((s) => {
    if (!s.rows?.length || s.rows.some((row) => !row.length)) throw new Error("Empty pipeline row");
    return [...s.rows.flat(), ...(s.sink ? [s.sink] : [])];
  });
  nodes.push(pipeline.output, ...pipeline.consumers);
  const ids = [...pipeline.stages.map((s) => s.id), ...nodes.map((n) => n.id)];
  if (new Set(ids).size !== ids.length) throw new Error("Duplicate pipeline ID");
  for (const edge of pipeline.edges ?? []) {
    if (!ids.includes(edge.from) || !ids.includes(edge.to) || edge.from === edge.to) {
      throw new Error("Invalid pipeline edge endpoint");
    }
    if (!["flow", "conditional", "bidirectional"].includes(edge.kind)) {
      throw new Error("Invalid pipeline edge kind");
    }
  }
}

// ---------------------------------------------------------------- layout

const L = {
  width: 900,
  padX: 14,
  /** Space between boxes in the same row. */
  gapX: 12,
  /** Wider gap for a two-box exchange, so the ⇄ arrow and its caption fit. */
  pairGapX: 130,
  /** Vertical space between rows inside one stage. */
  gapY: 30,
  /** Vertical space between stages (holds the connector bus + caption). */
  stageGapY: 40,
  boxPadY: 9,
  titleH: 15,
  lineH: 12,
  bandPadX: 10,
  bandPadTop: 26,
  bandPadBottom: 12,
  maxBoxW: 210,
  minBoxW: 96,
} as const;

export interface Box {
  node: PipelineNode;
  x: number;
  y: number;
  w: number;
  h: number;
}

export interface Band {
  stage: PipelineStage;
  x: number;
  y: number;
  w: number;
  h: number;
}

export interface Edge {
  /** Polyline points, already elbowed. */
  points: [number, number][];
  sourceId?: string;
  targetId?: string;
  labelPoint?: [number, number];
  labelAnchor?: "start" | "middle";
  dashed?: boolean;
  label?: string;
  /** Arrowhead at the end. Only the segment that lands on a box gets one. */
  arrow?: boolean;
  /** Draw arrowheads at both ends (the bull/bear exchange). */
  bidirectional?: boolean;
}

export interface Layout {
  width: number;
  height: number;
  bands: Band[];
  boxes: Box[];
  edges: Edge[];
}

function boxHeight(node: PipelineNode): number {
  return L.boxPadY * 2 + L.titleH + (node.lines?.length ?? 0) * L.lineH;
}

/** Lay a row of boxes out symmetrically inside [x, x + w]. */
function placeRow(
  nodes: PipelineNode[],
  x: number,
  w: number,
  y: number,
  gapX: number = L.gapX,
): Box[] {
  const boxW = Math.max(
    L.minBoxW,
    Math.min(L.maxBoxW, (w - gapX * (nodes.length - 1)) / nodes.length),
  );
  const total = boxW * nodes.length + gapX * (nodes.length - 1);
  const startX = x + (w - total) / 2;
  const h = Math.max(...nodes.map(boxHeight));
  return nodes.map((node, i) => ({
    node,
    x: startX + i * (boxW + gapX),
    y,
    w: boxW,
    h,
  }));
}

const bottomCenter = (b: Box): [number, number] => [b.x + b.w / 2, b.y + b.h];
const topCenter = (b: Box): [number, number] => [b.x + b.w / 2, b.y];

/**
 * Connect a set of source boxes to a set of target boxes through a horizontal
 * bus at the midpoint — the same shape mermaid draws, minus the spaghetti when
 * one node fans into four.
 */
function busEdges(from: Box[], to: Box[]): Edge[] {
  const yStart = Math.max(...from.map((b) => b.y + b.h));
  const yEnd = Math.min(...to.map((b) => b.y));
  const yBus = yStart + (yEnd - yStart) / 2;
  const edges: Edge[] = [];

  // A single straight line reads better than a stub-bus-stub when it is 1 → 1.
  if (from.length === 1 && to.length === 1) {
    const [x1] = bottomCenter(from[0]);
    const [x2] = topCenter(to[0]);
    if (Math.abs(x1 - x2) < 1) {
      return [
        {
          points: [
            [x1, yStart],
            [x2, yEnd],
          ],
          dashed: from[0].node.dashed,
          label: from[0].node.edgeLabel,
          arrow: true,
        },
      ];
    }
  }

  // Only the stubs that land on a box carry an arrowhead; stubs feeding the bus
  // would otherwise scatter arrowheads across empty space.
  for (const b of from) {
    const [x] = bottomCenter(b);
    edges.push({
      points: [
        [x, yStart],
        [x, yBus],
      ],
      dashed: b.node.dashed,
    });
  }
  const busXs = [...from.map((b) => b.x + b.w / 2), ...to.map((b) => b.x + b.w / 2)];
  const dashedBus = from.every((b) => b.node.dashed);
  edges.push({
    points: [
      [Math.min(...busXs), yBus],
      [Math.max(...busXs), yBus],
    ],
    dashed: dashedBus,
    label: from.length > 1 ? undefined : from[0].node.edgeLabel,
  });
  for (const b of to) {
    const [x] = topCenter(b);
    edges.push({
      points: [
        [x, yBus],
        [x, yEnd],
      ],
      dashed: dashedBus,
      arrow: true,
    });
  }
  return edges;
}

export function layoutPipeline(pipeline: Pipeline): Layout {
  validatePipeline(pipeline);
  const explicit = pipeline.edges !== undefined;
  const innerX = L.padX + L.bandPadX;
  const innerW = L.width - 2 * (L.padX + L.bandPadX);
  const bands: Band[] = [];
  const boxes: Box[] = [];
  const edges: Edge[] = [];
  let y = L.padX;
  /** Boxes the next thing down should connect from. */
  let prevExit: Box[] = [];

  for (const stage of pipeline.stages) {
    const bandTop = y;
    let rowY = bandTop + L.bandPadTop;
    let stageEntry: Box[] = [];
    let lastRow: Box[] = [];

    stage.rows.forEach((row, rowIdx) => {
      // A labelled exchange between two boxes needs room for the arrow + caption.
      const isPair = row.length === 2 && !!stage.pairLabel;
      const placed = placeRow(row, innerX, innerW, rowY, isPair ? L.pairGapX : L.gapX);
      boxes.push(...placed);
      if (rowIdx === 0) stageEntry = placed;
      else if (!explicit) edges.push(...busEdges(lastRow, placed));

      // The bull/bear exchange: a double-headed arrow between the two boxes.
      if (!explicit && placed.length === 2 && stage.pairLabel) {
        const [a, b] = placed;
        const yMid = rowY + a.h / 2;
        edges.push({
          points: [
            [a.x + a.w, yMid],
            [b.x, yMid],
          ],
          bidirectional: true,
          label: stage.pairLabel,
        });
      }

      lastRow = placed;
      rowY += placed[0].h + L.gapY;
    });

    if (stage.sink) {
      const placed = placeRow([stage.sink], innerX, innerW, rowY);
      boxes.push(...placed);
      if (!explicit) edges.push(...busEdges(lastRow, placed));
      lastRow = placed;
      rowY += placed[0].h + L.gapY;
    }

    const bandBottom = rowY - L.gapY + L.bandPadBottom;
    bands.push({
      stage,
      x: L.padX,
      y: bandTop,
      w: L.width - 2 * L.padX,
      h: bandBottom - bandTop,
    });

    if (!explicit && prevExit.length) edges.push(...busEdges(prevExit, stageEntry));
    prevExit = lastRow;
    y = bandBottom + L.stageGapY;
  }

  const outputBoxes = placeRow([pipeline.output], innerX, innerW, y);
  boxes.push(...outputBoxes);
  if (!explicit && prevExit.length) edges.push(...busEdges(prevExit, outputBoxes));
  y += outputBoxes[0].h + L.stageGapY;

  if (pipeline.consumers.length) {
    const consumerBoxes = placeRow(pipeline.consumers, innerX, innerW, y);
    boxes.push(...consumerBoxes);
    if (!explicit) edges.push(...busEdges(outputBoxes, consumerBoxes));
    y += consumerBoxes[0].h;
  }

  let width: number = L.width;
  if (explicit) {
    const anchors = new Map(boxes.map((b) => [b.node.id, b]));
    for (const band of bands) {
      anchors.set(band.stage.id, {
        ...band, node: { id: band.stage.id, label: band.stage.title },
      });
    }
    let bypass = 0;
    for (const connection of pipeline.edges ?? []) {
      const source = anchors.get(connection.from)!;
      const target = anchors.get(connection.to)!;
      const edge: Edge = {
        points: [], sourceId: connection.from, targetId: connection.to,
        dashed: connection.kind === "conditional",
        bidirectional: connection.kind === "bidirectional", arrow: true,
        label: connection.label,
      };
      if (Math.abs(source.y - target.y) < 1) {
        edge.points = [[source.x + source.w, source.y + source.h / 2],
          [target.x, target.y + target.h / 2]];
      } else {
        const a = bottomCenter(source);
        const b = topCenter(target);
        const obstruction = boxes.some((box) =>
          box.y > a[1] && box.y + box.h < b[1] &&
          box.x < Math.max(a[0], b[0]) + 1 &&
          box.x + box.w > Math.min(a[0], b[0]) - 1,
        );
        if (obstruction) {
          const lane = L.width + L.gapX * (1 + bypass++);
          const start: [number, number] = [source.x + source.w, source.y + source.h / 2];
          const end: [number, number] = [target.x + target.w, target.y + target.h / 2];
          edge.points = [start, [lane, start[1]], [lane, end[1]], end];
          edge.labelPoint = [lane + 8, (start[1] + end[1]) / 2];
          edge.labelAnchor = "start";
          width = Math.max(width, lane + 24 + (connection.label?.length ?? 0) * 6);
        } else if (Math.abs(a[0] - b[0]) < 1) {
          edge.points = [a, b];
        } else {
          const bus = (a[1] + b[1]) / 2;
          edge.points = [a, [a[0], bus], [b[0], bus], b];
        }
      }
      edges.push(edge);
    }
  }
  return { width, height: y + L.padX, bands, boxes, edges };
}

export const LAYOUT_CONSTANTS = L;
