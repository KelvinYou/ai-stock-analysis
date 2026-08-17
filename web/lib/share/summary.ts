import { describeConviction, type ConvictionSummary } from "@/lib/conviction";
import type { ActionPlan, TickerBundle } from "@/lib/types";

/**
 * Everything derived from a `TickerBundle` that a share surface needs, pulled
 * out of `ShareCard` so the plain-text summary (`buildShareText`) computes the
 * same numbers from the same rules instead of re-deriving them by hand and
 * drifting the moment one side changes.
 */
export interface CardSummary {
  currency: string;
  latestPrice: number | null;
  changePct: number | null;
  conviction: ConvictionSummary | null;
  plan: ActionPlan | null;
  hasLevels: boolean;
  thesis: string;
  asOf: string | undefined;
}

export function buildCardSummary(bundle: TickerBundle): CardSummary {
  const info = bundle.fundamentals?.info;
  const currency = info?.currency ?? "USD";

  const latestPrice = bundle.priceHistory.at(-1)?.close ?? bundle.technicals?.close ?? null;
  const prevPrice = bundle.priceHistory.at(-2)?.close ?? null;
  const changePct =
    latestPrice != null && prevPrice != null && prevPrice !== 0
      ? ((latestPrice - prevPrice) / prevPrice) * 100
      : null;

  const briefing = bundle.briefing;
  const conviction = briefing ? describeConviction(briefing) : null;
  const plan = briefing?.action_plan ?? null;
  const hasLevels =
    !!plan &&
    (plan.entry_limit !== null || plan.stop_loss !== null || plan.take_profit_1 !== null);

  const thesis = briefing
    ? (briefing.research_verdict?.thesis ?? briefing.executive_summary ?? "")
    : "";

  const asOf = briefing?.date ?? bundle.technicals?.as_of_date ?? bundle.priceHistory.at(-1)?.date;

  return { currency, latestPrice, changePct, conviction, plan, hasLevels, thesis, asOf };
}
