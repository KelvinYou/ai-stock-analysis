import { Suspense } from "react";
import Link from "next/link";
import { TickerBrowser } from "@/components/ticker-list/ticker-browser";
import { DataStatus } from "@/components/shared/data-status";
import { EmptyState } from "@/components/shared/empty-state";
import { listTickerSummaries } from "@/lib/data";
import { loadWatchlist } from "@/lib/watchlist";

// Data is plain JSON on disk; a short window keeps a fresh `stock-fetch` visible
// without a restart while still batching reads across a burst of navigation.
export const revalidate = 60;

export default async function ScreenerPage() {
  const [tickers, watchlist] = await Promise.all([
    listTickerSummaries(),
    loadWatchlist(),
  ]);

  if (tickers.length === 0) {
    return <EmptyState />;
  }

  return (
    <div className="space-y-6">
      <section className="fade-up space-y-4">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight text-ink md:text-3xl">
              Screener
            </h1>
            <p className="mt-1 text-sm text-graphite">
              Every watchlist ticker, one row each. Sort by any column.
            </p>
          </div>
          <Link
            href="/about"
            className="text-xs text-graphite underline-offset-4 hover:text-action hover:underline"
          >
            How the pipeline works →
          </Link>
        </div>

        <DataStatus tickers={tickers} watchlist={watchlist} />
      </section>

      <section aria-labelledby="all-tickers">
        <h2 id="all-tickers" className="sr-only">
          Browse tickers
        </h2>
        <Suspense fallback={<div className="h-12 animate-pulse rounded-lg bg-muted" />}>
          <TickerBrowser tickers={tickers} />
        </Suspense>
      </section>
    </div>
  );
}
