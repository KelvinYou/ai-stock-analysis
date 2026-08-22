import Link from "next/link";
import { readAttention, type AttentionKind } from "@/lib/book";
import { cn } from "@/lib/utils";
import type { TickerNavSummary } from "@/lib/types";

/**
 * The rail's action queue: only tickers waiting on a decision. Short by design —
 * an empty queue is a good result and says so rather than showing nothing.
 */

const KIND: Record<AttentionKind, { glyph: string; tone: string; sr: string }> = {
  stop: {
    glyph: "▼",
    tone: "text-bear",
    sr: "Price has breached the stop loss — the thesis is invalidated",
  },
  target: {
    glyph: "◆",
    tone: "text-bull",
    sr: "Price has reached the first take-profit target",
  },
  "at-entry": {
    glyph: "▲",
    tone: "text-bull",
    sr: "Price has reached the entry limit",
  },
  stale: {
    glyph: "°",
    tone: "text-halt",
    sr: "Briefing is overdue for a re-run",
  },
};

export function NeedsALook({
  tickers,
  onNavigate,
  max = 5,
}: {
  tickers: TickerNavSummary[];
  onNavigate?: () => void;
  max?: number;
}) {
  const all = readAttention(tickers);
  const items = all.slice(0, max);
  const hidden = all.length - items.length;

  return (
    <div className="px-2 py-3">
      <div className="flex items-baseline justify-between gap-2 px-3">
        <h2 className="eyebrow">Needs a look</h2>
        {all.length > 0 && (
          <span className="num text-mini text-graphite">{all.length}</span>
        )}
      </div>

      {items.length === 0 ? (
        <p className="mt-1.5 px-3 text-micro text-graphite">
          Nothing waiting. Every briefing is current and no ticker has reached its
          entry.
        </p>
      ) : (
        <ul className="mt-1">
          {items.map((item) => {
            const kind = KIND[item.kind];
            return (
              <li key={`${item.symbol}-${item.kind}`}>
                <Link
                  href={`/${item.symbol}`}
                  onClick={onNavigate}
                  className="group flex items-center gap-2.5 rounded px-3 py-1.5 transition-colors hover:bg-secondary"
                >
                  <span
                    className={cn("w-3 shrink-0 text-center text-mini leading-none", kind.tone)}
                    aria-hidden
                  >
                    {kind.glyph}
                  </span>
                  <span className="num shrink-0 text-xs font-medium text-ink">
                    {item.symbol}
                  </span>
                  <span className="sr-only">{kind.sr}.</span>
                  <span className="min-w-0 flex-1 truncate text-mini text-graphite">
                    {item.label}
                  </span>
                  {item.value && (
                    <span className={cn("num shrink-0 text-mini", kind.tone)}>
                      {item.value}
                    </span>
                  )}
                </Link>
              </li>
            );
          })}
          {hidden > 0 && (
            <li className="px-3 pt-1">
              <Link
                href="/"
                onClick={onNavigate}
                className="text-mini text-graphite transition-colors hover:text-action"
              >
                {hidden} more in the screener →
              </Link>
            </li>
          )}
        </ul>
      )}
    </div>
  );
}
