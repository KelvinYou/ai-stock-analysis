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
  if (signal === "strong_buy" || signal === "buy") return "bull";
  if (signal === "strong_sell" || signal === "sell") return "bear";
  return "neutral";
}

const DIRECTION_LABEL: Record<Direction, string> = {
  bull: "Buy",
  bear: "Sell",
  neutral: "Hold",
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
