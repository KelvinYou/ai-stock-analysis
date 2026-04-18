import Link from "next/link";
import { notFound } from "next/navigation";
import { ChevronLeft } from "lucide-react";
import { Card } from "@/components/ui/card";
import { PriceChart } from "@/components/price-chart";
import { SignalBadge } from "@/components/signal-badge";
import { AnalystSection } from "@/components/sections/analyst-section";
import { BriefingSection } from "@/components/sections/briefing-section";
import { DebateSection } from "@/components/sections/debate-section";
import { FundamentalsSection } from "@/components/sections/fundamentals-section";
import { TechnicalsSection } from "@/components/sections/technicals-section";
import { listTickers, loadTicker } from "@/lib/data";
import { fmtCurrency, fmtSignedPercent } from "@/lib/format";
import { cn } from "@/lib/utils";

export const revalidate = 0;

export async function generateStaticParams() {
  const tickers = await listTickers();
  return tickers.map((ticker) => ({ ticker }));
}

export default async function TickerPage({
  params,
}: {
  params: Promise<{ ticker: string }>;
}) {
  const { ticker } = await params;
  const bundle = await loadTicker(ticker);
  if (!bundle || (!bundle.fundamentals && !bundle.technicals && bundle.priceHistory.length === 0)) {
    notFound();
  }

  const info = bundle.fundamentals?.info;
  const currency = info?.currency ?? "USD";
  const latestPrice =
    bundle.priceHistory.at(-1)?.close ?? bundle.technicals?.close ?? null;
  const prevPrice = bundle.priceHistory.at(-2)?.close ?? null;
  const changePct =
    latestPrice != null && prevPrice != null && prevPrice !== 0
      ? ((latestPrice - prevPrice) / prevPrice) * 100
      : null;
  const up = (changePct ?? 0) >= 0;

  const sections: { id: string; label: string; show: boolean }[] = [
    { id: "chart", label: "Price", show: bundle.priceHistory.length > 0 },
    { id: "briefing", label: "Briefing", show: !!bundle.briefing },
    { id: "analysts", label: "Analysts", show: !!bundle.analystReports },
    { id: "debate", label: "Debate", show: !!bundle.debate },
    { id: "fundamentals", label: "Fundamentals", show: !!bundle.fundamentals },
    { id: "technicals", label: "Technicals", show: !!bundle.technicals },
  ].filter((s) => s.show);

  return (
    <div className="space-y-8">
      <Link
        href="/"
        className="inline-flex items-center gap-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground"
      >
        <ChevronLeft className="size-4" />
        All tickers
      </Link>

      <header className="flex flex-wrap items-start justify-between gap-6 border-b border-border/60 pb-6">
        <div className="space-y-2">
          <div className="flex items-center gap-3">
            <h1 className="font-mono text-4xl font-bold tracking-tight md:text-5xl">
              {bundle.symbol}
            </h1>
            <span className="rounded border border-border/60 bg-muted/40 px-2 py-0.5 text-xs uppercase tracking-wider text-muted-foreground">
              {info?.market ?? "—"}
            </span>
            {bundle.briefing && (
              <SignalBadge
                signal={bundle.briefing.overall_signal}
                size="lg"
              />
            )}
          </div>
          <div className="text-xl text-muted-foreground">{info?.name ?? bundle.symbol}</div>
          <div className="flex flex-wrap gap-x-4 gap-y-1 text-sm text-muted-foreground">
            {info?.sector && <span>{info.sector}</span>}
            {info?.industry && <span>· {info.industry}</span>}
          </div>
        </div>
        <div className="text-right">
          <div className="num text-3xl font-semibold tracking-tight md:text-4xl">
            {fmtCurrency(latestPrice, currency)}
          </div>
          {changePct != null && (
            <div className={cn("num text-sm", up ? "text-emerald-400" : "text-rose-400")}>
              {fmtSignedPercent(changePct)} previous close
            </div>
          )}
        </div>
      </header>

      {sections.length > 1 && (
        <nav className="sticky top-14 z-30 -mx-4 mb-2 border-b border-border/50 bg-background/80 px-4 py-2 backdrop-blur">
          <div className="flex gap-1 overflow-x-auto text-sm">
            {sections.map((s) => (
              <a
                key={s.id}
                href={`#${s.id}`}
                className="whitespace-nowrap rounded-md px-3 py-1.5 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
              >
                {s.label}
              </a>
            ))}
          </div>
        </nav>
      )}

      <div className="space-y-6">
        {bundle.priceHistory.length > 0 && (
          <Card id="chart" className="scroll-mt-28 p-6 md:p-8">
            <PriceChart data={bundle.priceHistory} currency={currency} />
          </Card>
        )}

        {bundle.briefing && <BriefingSection data={bundle.briefing} />}
        {bundle.analystReports && <AnalystSection data={bundle.analystReports} />}
        {bundle.debate && <DebateSection data={bundle.debate} />}
        {bundle.fundamentals && <FundamentalsSection data={bundle.fundamentals} />}
        {bundle.technicals && <TechnicalsSection data={bundle.technicals} />}
      </div>
    </div>
  );
}
