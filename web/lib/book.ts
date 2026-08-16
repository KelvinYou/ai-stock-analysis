import type { Signal, TickerSummary } from "@/lib/types";
import { signalDirection, signalPosition } from "@/lib/conviction";

/**
 * Two readings of the whole watchlist at once, for the persistent rail.
 *
 * The screener already answers "how does each ticker rank" — a rail that
 * re-sorts the same rows adds nothing. These answer the two questions a table
 * structurally cannot: what shape is the book in, and what is waiting on me.
 */

/** A briefing older than this is worth re-running before acting on it. */
export const STALE_BRIEFING_DAYS = 5;

export interface BookShape {
  tracked: number;
  /** Every briefed ticker's conviction, ascending — the ticks on the axis. */
  convictions: number[];
  buy: number;
  hold: number;
  sell: number;
  median: number | null;
}

export function readBook(tickers: TickerSummary[]): BookShape {
  const briefed = tickers.filter((t) => t.conviction != null && t.signal != null);
  const convictions = briefed
    .map((t) => Math.max(-1, Math.min(1, t.conviction!)))
    .sort((a, b) => a - b);

  let buy = 0;
  let hold = 0;
  let sell = 0;
  for (const t of briefed) {
    const p = signalPosition(t.signal as Signal);
    if (p > 0) buy += 1;
    else if (p < 0) sell += 1;
    else hold += 1;
  }

  const median = convictions.length
    ? convictions.length % 2
      ? convictions[(convictions.length - 1) / 2]
      : (convictions[convictions.length / 2 - 1] + convictions[convictions.length / 2]) / 2
    : null;

  return { tracked: briefed.length, convictions, buy, hold, sell, median };
}

export type AttentionKind = "target" | "stop" | "at-entry" | "stale";

export interface AttentionItem {
  symbol: string;
  kind: AttentionKind;
  /** Shown to the reader; states the reason, never just a colour. */
  label: string;
  /** Trailing value, already formatted. Null when the label says it all. */
  value: string | null;
}

/**
 * Only events, never standing states.
 *
 * Low convergence is deliberately NOT here: 11 of 26 names sit below the
 * threshold on a normal day, so it drowns the queue, and the screener's Cvg
 * column already flags it. What belongs here is price crossing a level the
 * pipeline itself quoted — nothing else in the app watches for that.
 *
 * Ordered by urgency: a breached stop invalidates a thesis, a hit target wants
 * action today, an entry reached is an opportunity, a stale briefing is merely
 * overdue.
 */
export function readAttention(tickers: TickerSummary[]): AttentionItem[] {
  const stops: AttentionItem[] = [];
  const targets: AttentionItem[] = [];
  const entries: AttentionItem[] = [];
  const stale: AttentionItem[] = [];

  for (const t of tickers) {
    const dir = signalDirection(t.signal);
    const price = t.price;

    // Levels sit on opposite sides depending on which way the thesis runs, so a
    // plain `price <= stop` would fire constantly on every short.
    if (price != null && dir !== "neutral") {
      const breached =
        dir === "bull"
          ? t.stopLoss != null && price <= t.stopLoss
          : t.stopLoss != null && price >= t.stopLoss;
      if (breached) {
        stops.push({
          symbol: t.symbol,
          kind: "stop",
          label: "stop breached",
          value: fmtLevel(price),
        });
        continue; // A breached stop supersedes its own target.
      }

      const hit =
        dir === "bull"
          ? t.takeProfit1 != null && price >= t.takeProfit1
          : t.takeProfit1 != null && price <= t.takeProfit1;
      if (hit) {
        targets.push({
          symbol: t.symbol,
          kind: "target",
          label: "target hit",
          value: fmtLevel(price),
        });
        continue;
      }
    }

    if (t.toEntryPct != null && t.toEntryPct >= 0) {
      entries.push({
        symbol: t.symbol,
        kind: "at-entry",
        label: "at entry",
        value: `+${t.toEntryPct.toFixed(1)}%`,
      });
    }
  }

  for (const t of tickers) {
    if (t.briefingAgeDays != null && t.briefingAgeDays > STALE_BRIEFING_DAYS) {
      stale.push({
        symbol: t.symbol,
        kind: "stale",
        label: `briefing ${t.briefingAgeDays}d old`,
        value: null,
      });
    }
  }

  return [...stops, ...targets, ...entries, ...stale];
}

function fmtLevel(price: number): string {
  return price >= 100 ? price.toFixed(0) : price.toFixed(2);
}
