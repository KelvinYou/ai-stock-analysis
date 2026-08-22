import { readBook } from "@/lib/book";
import { cn } from "@/lib/utils";
import type { TickerNavSummary } from "@/lib/types";

/**
 * The whole watchlist on the same Sell↔Buy axis the ticker page uses, one tick
 * per briefed name. The screener ranks rows; this shows the shape they make —
 * a cluster at neutral means the book has no strong view, a mass on one side
 * means it is committed. Reads in a glance at rail width.
 */

/** −1…+1 → 0…100% across the axis. */
function pct(position: number) {
  return ((position + 1) / 2) * 100;
}

export function BookShape({ tickers }: { tickers: TickerNavSummary[] }) {
  const book = readBook(tickers);
  if (book.briefed === 0) return null;

  const summary =
    `${book.briefed} briefed: ${book.buy} buy, ${book.hold} hold, ${book.sell} sell.` +
    (book.median != null ? ` Median conviction ${book.median.toFixed(2)}.` : "");

  return (
    <figure className="m-0 px-5 py-3">
      <div className="flex items-baseline justify-between gap-2">
        <figcaption className="eyebrow">Book shape</figcaption>
        <span className="num text-mini text-graphite">{book.briefed} briefed</span>
      </div>

      <div className="relative mt-3" role="img" aria-label={`Book shape. ${summary}`}>
        {/* Ticks sit at low opacity so overlap reads as density, not as one mark. */}
        <div className="relative h-6">
          {book.convictions.map((c, i) => (
            <span
              key={i}
              className={cn(
                "absolute bottom-0 h-4 w-px",
                c > 0.05 ? "bg-bull" : c < -0.05 ? "bg-bear" : "bg-graphite",
                "opacity-70",
              )}
              style={{ left: `${pct(c)}%` }}
              aria-hidden
            />
          ))}
        </div>

        <div className="relative h-px bg-rule">
          <span
            className="absolute left-1/2 top-1/2 h-1.5 w-px -translate-x-1/2 -translate-y-1/2 bg-rule"
            aria-hidden
          />
        </div>

        {/* Median sits below the rule so it never reads as one more ticker. */}
        <div className="relative h-2">
          {book.median != null && (
            <span
              className="absolute top-0 h-2 w-px -translate-x-1/2 bg-ink"
              style={{ left: `${pct(book.median)}%` }}
              aria-hidden
            />
          )}
        </div>

        <div className="mt-1.5 flex justify-between text-mini uppercase tracking-[0.06em] text-graphite">
          <span>Sell</span>
          <span>Buy</span>
        </div>
      </div>

      <p className="mt-2 text-mini text-graphite">
        <span className="num text-bull">{book.buy}</span> buy ·{" "}
        <span className="num text-ink">{book.hold}</span> hold ·{" "}
        <span className="num text-bear">{book.sell}</span> sell
        {book.median != null && (
          <>
            {" · median "}
            <span className="num text-ink">
              {book.median >= 0 ? "+" : ""}
              {book.median.toFixed(2)}
            </span>
          </>
        )}
      </p>
    </figure>
  );
}
