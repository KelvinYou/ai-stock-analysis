import type { Signal, TickerSummary } from "./types";

/** A briefing older than this is flagged stale — the tape has moved on. */
export const STALE_DAYS = 5;
/** Below this, the desk spread deserves a debate read before acting. */
export const LOW_CONVERGENCE = 0.5;

export const SIGNAL_WEIGHT: Record<Signal, number> = {
  strong_buy: 2,
  buy: 1,
  neutral: 0,
  sell: -1,
  strong_sell: -2,
};

export type SortKey =
  | "symbol"
  | "name"
  | "price"
  | "signal"
  | "conviction"
  | "convergence"
  | "toEntry"
  | "riskReward"
  | "pe"
  | "rsi"
  | "from52wHigh"
  | "age";

export type SortDir = "asc" | "desc";

export interface ColumnDef {
  key: SortKey;
  /** Header text. Kept short — 15 columns have to fit. */
  label: string;
  /** Tooltip spelling out what the number means. */
  title: string;
  numeric: boolean;
  /** Direction a first click on this header should apply. */
  defaultDir: SortDir;
  /** Hide below this Tailwind breakpoint to keep phones usable. */
  hideBelow?: "sm" | "md" | "lg" | "xl";
}

export const COLUMNS: ColumnDef[] = [
  {
    key: "symbol",
    label: "Symbol",
    title: "Ticker symbol",
    numeric: false,
    defaultDir: "asc",
  },
  {
    key: "name",
    label: "Name",
    title: "Company name",
    numeric: false,
    defaultDir: "asc",
    hideBelow: "xl",
  },
  {
    key: "price",
    label: "Price",
    title: "Last close",
    numeric: true,
    defaultDir: "desc",
  },
  {
    key: "signal",
    label: "Signal",
    title: "Synthesizer's overall signal",
    numeric: false,
    defaultDir: "desc",
  },
  {
    key: "conviction",
    label: "Conv",
    title: "Conviction score, −1.00 (max bearish) to +1.00 (max bullish)",
    numeric: true,
    defaultDir: "desc",
  },
  {
    key: "convergence",
    label: "Cvg",
    title: "Signal convergence — 0 = the four analyst agents disagree, 1 = full agreement",
    numeric: true,
    defaultDir: "desc",
    hideBelow: "md",
  },
  {
    key: "toEntry",
    label: "→Entry",
    title:
      "Distance from last close to the suggested entry limit. Negative = price must still fall; ≥ 0 = already at or below entry",
    numeric: true,
    defaultDir: "desc",
  },
  {
    key: "riskReward",
    label: "R:R",
    title: "Risk/reward ratio from the risk assessment",
    numeric: true,
    defaultDir: "desc",
    hideBelow: "lg",
  },
  {
    key: "pe",
    label: "P/E",
    title: "Trailing price/earnings",
    numeric: true,
    defaultDir: "asc",
    hideBelow: "md",
  },
  {
    key: "rsi",
    label: "RSI",
    title: "RSI-14. Below 30 = oversold, above 70 = overbought",
    numeric: true,
    defaultDir: "asc",
    hideBelow: "sm",
  },
  {
    key: "from52wHigh",
    label: "52w",
    title: "Distance below the 52-week high",
    numeric: true,
    defaultDir: "asc",
    hideBelow: "lg",
  },
  {
    key: "age",
    label: "Age",
    title: "Days since this briefing was generated",
    numeric: true,
    defaultDir: "asc",
  },
];

/** Price has reached the suggested entry limit — the only rows you can act on today. */
export function isActionable(t: TickerSummary): boolean {
  return t.toEntryPct != null && t.toEntryPct >= 0;
}

export function isStale(t: Pick<TickerSummary, "briefingAgeDays">): boolean {
  return t.briefingAgeDays != null && t.briefingAgeDays > STALE_DAYS;
}

type SortValue = string | number | null;

function valueOf(t: TickerSummary, key: SortKey): SortValue {
  switch (key) {
    case "symbol":
      return t.symbol;
    case "name":
      return t.name;
    case "price":
      return t.price;
    case "signal":
      return t.signal ? SIGNAL_WEIGHT[t.signal] : null;
    case "conviction":
      return t.conviction;
    case "convergence":
      return t.convergence;
    case "toEntry":
      return t.toEntryPct;
    case "riskReward":
      return t.riskReward;
    case "pe":
      return t.peRatio;
    case "rsi":
      return t.rsi14;
    case "from52wHigh":
      return t.pctFrom52wHigh;
    case "age":
      return t.briefingAgeDays;
  }
}

/**
 * Sort rows, always keeping missing values last regardless of direction — a
 * ticker with no briefing should never outrank one that has one just because
 * you flipped to ascending.
 */
export function sortRows(
  rows: readonly TickerSummary[],
  key: SortKey,
  dir: SortDir,
): TickerSummary[] {
  const factor = dir === "asc" ? 1 : -1;
  return [...rows].sort((a, b) => {
    const av = valueOf(a, key);
    const bv = valueOf(b, key);
    if (av == null && bv == null) return a.symbol.localeCompare(b.symbol);
    if (av == null) return 1;
    if (bv == null) return -1;
    const cmp =
      typeof av === "string" && typeof bv === "string"
        ? av.localeCompare(bv)
        : (av as number) - (bv as number);
    if (cmp !== 0) return cmp * factor;
    return a.symbol.localeCompare(b.symbol);
  });
}
