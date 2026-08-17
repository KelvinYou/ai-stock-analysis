import { fmtCurrency } from "@/lib/format";
import type { TickerBundle } from "@/lib/types";
import { buildCardSummary } from "./summary";

/**
 * The plain-text counterpart to `ShareCard` — same underlying numbers via
 * `buildCardSummary`, shaped for a paste target that can't render an image:
 * an iMessage, a Slack line, a tweet. Always ends with the link, since text
 * without the card has nothing else pointing back at the briefing.
 */
export function buildShareText(bundle: TickerBundle, url: string): string {
  const { currency, plan, hasLevels, conviction } = buildCardSummary(bundle);

  const parts = [bundle.symbol];

  if (conviction) {
    parts.push(conviction.phrase);
  }

  if (hasLevels && plan) {
    const levels = [
      plan.entry_limit !== null && `Entry ${fmtCurrency(plan.entry_limit, currency)}`,
      plan.stop_loss !== null && `Stop ${fmtCurrency(plan.stop_loss, currency)}`,
      plan.take_profit_1 !== null && `Target ${fmtCurrency(plan.take_profit_1, currency)}`,
    ].filter(Boolean);
    if (levels.length) parts.push(levels.join(" / "));
  }

  return `${parts.join(" · ")}\n${url}`;
}
