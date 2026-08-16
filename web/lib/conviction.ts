import type { Briefing } from "@/lib/types";
import type { Signal } from "@/lib/types";

export type ConvictionTone = "strong" | "moderate" | "weak" | "mixed";
export type Direction = "bull" | "bear" | "neutral";

export interface ConvictionSummary {
  phrase: string;
  tone: ConvictionTone;
  agreement: {
    agreeing: number;
    total: number;
    direction: Direction;
  };
}

export function signalDirection(signal: string | null | undefined): Direction {
  if (!signal) return "neutral";
  const token = signal.trim().toLowerCase().match(/^(strong[ _]buy|strong[ _]sell|buy|sell|hold|neutral)/)?.[1];
  if (!token) return "neutral";
  const normalized = token.replace(" ", "_");
  if (normalized === "strong_buy" || normalized === "buy") return "bull";
  if (normalized === "strong_sell" || normalized === "sell") return "bear";
  return "neutral";
}

/**
 * Where a signal sits on the consensus axis, −1 (strong sell) to +1 (strong buy).
 * The axis is the page's one piece of chroma, so this mapping is what every
 * coloured mark in the UI ultimately derives from.
 */
const SIGNAL_POSITION: Record<string, number> = {
  strong_sell: -1,
  sell: -0.5,
  hold: 0,
  neutral: 0,
  buy: 0.5,
  strong_buy: 1,
};

export function signalPosition(signal: string | null | undefined): number {
  if (!signal) return 0;
  const key = signal.trim().toLowerCase().replace(/[ -]/g, "_");
  return SIGNAL_POSITION[key] ?? 0;
}

export interface AnalystMark {
  /** Desk name as shown to the reader, e.g. "Fundamentals". */
  desk: string;
  /** Axis-width label — full names collide once two desks sit near each other. */
  abbr: string;
  signal: string;
  position: number;
  direction: Direction;
}

export interface ConsensusReading {
  marks: AnalystMark[];
  /** Narrowest and widest analyst positions — the visible spread. */
  spread: { min: number; max: number; width: number } | null;
  conviction: number;
  convergence: number;
  /** True when convergence was too low for the pipeline to quote levels. */
  levelsWithheld: boolean;
}

const DESK_LABEL: Record<string, string> = {
  fundamentals: "Fundamentals",
  sentiment: "Sentiment",
  technical: "Technical",
  macro: "Macro / FX",
};

const DESK_ABBR: Record<string, string> = {
  fundamentals: "Fund",
  sentiment: "Sent",
  technical: "Tech",
  macro: "Macro",
};

export function readConsensus(briefing: Briefing): ConsensusReading {
  const breakdown = briefing.agent_signal_breakdown ?? {};
  const marks: AnalystMark[] = Object.entries(breakdown)
    .filter(([, signal]) => !!signal)
    .map(([desk, signal]) => ({
      desk: DESK_LABEL[desk] ?? desk,
      abbr: DESK_ABBR[desk] ?? (DESK_LABEL[desk] ?? desk),
      signal: String(signal),
      position: signalPosition(String(signal)),
      direction: signalDirection(String(signal)),
    }));

  const positions = marks.map((m) => m.position);
  const spread = positions.length
    ? {
        min: Math.min(...positions),
        max: Math.max(...positions),
        width: Math.max(...positions) - Math.min(...positions),
      }
    : null;

  const plan = briefing.action_plan;
  const levelsWithheld =
    !plan ||
    (plan.entry_limit === null &&
      plan.stop_loss === null &&
      plan.take_profit_1 === null);

  return {
    marks,
    spread,
    conviction: Math.max(-1, Math.min(1, briefing.conviction.score)),
    convergence: briefing.conviction.signal_convergence,
    levelsWithheld,
  };
}

/**
 * The one-word verdict, and the line that qualifies it. Exported because the
 * decision card and the share card must never disagree about what a briefing
 * says — they are the same claim rendered by two different engines.
 *
 * Hold is a complete answer, not a missing one; nothing here softens it.
 */
export const DIRECTION_LABEL: Record<Direction, string> = {
  bull: "Buy",
  bear: "Sell",
  neutral: "Hold",
};

export const TONE_EYEBROW: Record<ConvictionTone, string> = {
  strong: "High conviction",
  moderate: "Moderate conviction",
  weak: "Slight lean",
  mixed: "The desks disagree",
};

export function describeConviction(briefing: Briefing): ConvictionSummary {
  const direction = signalDirection(briefing.overall_signal);

  const entries = Object.values(briefing.agent_signal_breakdown ?? {});
  const total = entries.length;
  const agreeing = entries.reduce(
    (acc, v) => (signalDirection(v) === direction ? acc + 1 : acc),
    0,
  );

  const magnitude = Math.abs(briefing.conviction.score);
  const convergence = briefing.conviction.signal_convergence;

  let tone: ConvictionTone;
  if (convergence < 0.5 || (total > 0 && agreeing / total < 0.5)) {
    tone = "mixed";
  } else if (magnitude >= 0.6) {
    tone = "strong";
  } else if (magnitude >= 0.3) {
    tone = "moderate";
  } else if (magnitude >= 0.1) {
    tone = "weak";
  } else {
    tone = "mixed";
  }

  const label = DIRECTION_LABEL[direction];
  let phrase: string;
  if (tone === "mixed" || direction === "neutral") {
    phrase = direction === "neutral" ? "Mixed signals — Hold" : `Mixed signals — leaning ${label}`;
  } else if (tone === "strong") {
    phrase = `Strong conviction — ${label}`;
  } else if (tone === "moderate") {
    phrase = `Moderate conviction — ${label}`;
  } else {
    phrase = `Leaning ${label}`;
  }

  return {
    phrase,
    tone,
    agreement: { agreeing, total, direction },
  };
}

export function overallSignalDirection(signal: Signal): Direction {
  return signalDirection(signal);
}
