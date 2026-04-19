import { Suspense } from "react";
import { TickerBrowser } from "@/components/ticker-list/ticker-browser";
import { EmptyState } from "@/components/shared/empty-state";
import { listTickerSummaries } from "@/lib/data";
import { cn } from "@/lib/utils";

export const revalidate = 3600;

export default async function DashboardPage() {
  const tickers = await listTickerSummaries();

  if (tickers.length === 0) {
    return <EmptyState />;
  }

  const bullish = tickers.filter(
    (t) => t.signal === "buy" || t.signal === "strong_buy",
  ).length;
  const bearish = tickers.filter(
    (t) => t.signal === "sell" || t.signal === "strong_sell",
  ).length;
  const withConviction = tickers.filter((t) => t.conviction != null);
  const avgConviction =
    withConviction.length > 0
      ? withConviction.reduce((s, t) => s + (t.conviction ?? 0), 0) /
        withConviction.length
      : 0;

  return (
    <div className="space-y-10">
      <section className="fade-up">
        <h1 className="text-2xl font-semibold tracking-tight text-foreground md:text-3xl">
          Briefings
        </h1>
        <p className="mt-2 max-w-xl text-sm leading-relaxed text-muted-foreground">
          Four specialist agents — fundamentals, technicals, sentiment, macro — read the tape
          independently. Bull and bear debate. A synthesizer arbitrates.
        </p>

        <div className="mt-6 grid max-w-md grid-cols-3 gap-3">
          <SummaryStat label="Tickers" value={String(tickers.length)} />
          <SummaryStat
            label="Bull / Bear"
            value={`${bullish} / ${bearish}`}
            tone={bullish >= bearish ? "bull" : "bear"}
          />
          <SummaryStat
            label="Conviction"
            value={`${avgConviction >= 0 ? "+" : ""}${avgConviction.toFixed(2)}`}
            tone={
              avgConviction > 0.15 ? "bull" : avgConviction < -0.15 ? "bear" : "muted"
            }
          />
        </div>
      </section>

      <section aria-labelledby="all-tickers">
        <h2
          id="all-tickers"
          className="mb-4 text-sm font-semibold tracking-tight text-foreground"
        >
          Browse tickers
        </h2>
        <Suspense fallback={<div className="h-12 animate-pulse rounded-lg bg-muted" />}>
          <TickerBrowser tickers={tickers} />
        </Suspense>
      </section>
    </div>
  );
}

function SummaryStat({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone?: "bull" | "bear" | "muted";
}) {
  const tint =
    tone === "bull"
      ? "text-emerald-600"
      : tone === "bear"
        ? "text-rose-600"
        : "text-foreground";
  return (
    <div className="rounded-lg border bg-card p-3">
      <div className="text-[11px] font-medium text-muted-foreground">{label}</div>
      <div className={cn("num mt-1 text-base font-semibold tracking-tight", tint)}>
        {value}
      </div>
    </div>
  );
}
