import { notFound } from "next/navigation";
import { PriceChart } from "@/components/chart/price-chart";
import { DecisionCard } from "@/components/briefing/decision-card";
import { AnalystSection } from "@/components/briefing/section-analysts";
import { BriefingSection } from "@/components/briefing/section-briefing";
import { DebateSection } from "@/components/briefing/section-debate";
import { FundamentalsSection } from "@/components/briefing/section-fundamentals";
import { TechnicalsSection } from "@/components/briefing/section-technicals";
import { SectionCard } from "@/components/shared/section-card";
import { listTickers, loadTicker } from "@/lib/data";
import { fmtCurrency, fmtSignedPercent } from "@/lib/format";
import { cn } from "@/lib/utils";

export const revalidate = 3600;

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
    { id: "fundamentals", label: "Fundamentals", show: !!bundle.fundamentals },
    { id: "technicals", label: "Technicals", show: !!bundle.technicals },
    { id: "briefing", label: "Brief", show: !!bundle.briefing },
    { id: "analysts", label: "Analysts", show: !!bundle.analystReports },
    { id: "debate", label: "Debate", show: !!bundle.debate },
  ].filter((s) => s.show);

  return (
    <div className="space-y-8">
      <header className="fade-up space-y-5">
        <div className="flex flex-wrap items-start justify-between gap-6">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <h1 className="num text-2xl font-semibold tracking-tight text-foreground md:text-3xl">
                {bundle.symbol}
              </h1>
              {info?.market && (
                <span className="rounded-md bg-muted px-1.5 py-0.5 text-[11px] font-medium text-muted-foreground">
                  {info.market}
                </span>
              )}
            </div>
            <p className="mt-1 truncate text-sm text-muted-foreground">
              {info?.name ?? bundle.symbol}
            </p>
            <div className="mt-3 flex flex-wrap items-center gap-2">
              {info?.sector && (
                <span className="rounded-full border px-2.5 py-0.5 text-[11px] text-muted-foreground">
                  {info.sector}
                </span>
              )}
              {info?.industry && (
                <span className="rounded-full border px-2.5 py-0.5 text-[11px] text-muted-foreground">
                  {info.industry}
                </span>
              )}
            </div>
          </div>

          <div className="text-right">
            <div className="text-[11px] font-medium text-muted-foreground">Last close</div>
            <div className="num mt-1 text-2xl font-semibold tracking-tight text-foreground md:text-3xl">
              {fmtCurrency(latestPrice, currency)}
            </div>
            {changePct != null && (
              <div
                className={cn(
                  "num mt-0.5 text-xs font-medium",
                  up ? "text-emerald-600" : "text-rose-600",
                )}
              >
                {up ? "+" : ""}
                {fmtSignedPercent(changePct)}{" "}
                <span className="text-muted-foreground">vs previous</span>
              </div>
            )}
          </div>
        </div>

        {bundle.briefing && (
          <DecisionCard briefing={bundle.briefing} currency={currency} />
        )}
      </header>

      {sections.length > 1 && (
        <nav
          aria-label="Sections on this page"
          className="sticky top-16 z-20 -mx-5 border-y bg-background/80 px-5 py-2 backdrop-blur-md md:-mx-10 md:px-10"
        >
          <div className="flex items-center gap-1 overflow-x-auto">
            {sections.map((s) => (
              <a
                key={s.id}
                href={`#${s.id}`}
                className="inline-flex shrink-0 items-center rounded-md px-3 py-1.5 text-xs font-medium text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
              >
                {s.label}
              </a>
            ))}
          </div>
        </nav>
      )}

      <div className="space-y-8">
        {bundle.priceHistory.length > 0 && (
          <SectionCard id="chart" title="Price" description="Daily close">
            <PriceChart data={bundle.priceHistory} currency={currency} />
          </SectionCard>
        )}

        {bundle.fundamentals && <FundamentalsSection data={bundle.fundamentals} />}
        {bundle.technicals && <TechnicalsSection data={bundle.technicals} />}
        {bundle.briefing && <BriefingSection data={bundle.briefing} currency={currency} />}
        {bundle.analystReports && <AnalystSection data={bundle.analystReports} />}
        {bundle.debate && <DebateSection data={bundle.debate} />}
      </div>
    </div>
  );
}
