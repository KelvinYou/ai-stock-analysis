import { notFound } from "next/navigation";
import { PriceChart } from "@/components/chart/price-chart";
import { SignalBadge } from "@/components/briefing/signal-badge";
import { AnalystSection } from "@/components/briefing/section-analysts";
import { BriefingSection } from "@/components/briefing/section-briefing";
import { DebateSection } from "@/components/briefing/section-debate";
import { FundamentalsSection } from "@/components/briefing/section-fundamentals";
import { TechnicalsSection } from "@/components/briefing/section-technicals";
import { SectionCard } from "@/components/shared/section-card";
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

  const sections: { id: string; label: string; num: string; show: boolean }[] = [
    { id: "chart", label: "Price", num: "01", show: bundle.priceHistory.length > 0 },
    { id: "briefing", label: "Brief", num: "02", show: !!bundle.briefing },
    { id: "analysts", label: "Analysts", num: "03", show: !!bundle.analystReports },
    { id: "debate", label: "Debate", num: "04", show: !!bundle.debate },
    { id: "fundamentals", label: "Fundamentals", num: "05", show: !!bundle.fundamentals },
    { id: "technicals", label: "Technicals", num: "06", show: !!bundle.technicals },
  ].filter((s) => s.show);

  const today = new Date().toLocaleDateString("en-US", {
    weekday: "short",
    month: "short",
    day: "numeric",
    year: "numeric",
  });

  return (
    <div className="space-y-10">
      {/* Masthead */}
      <header className="rise-in space-y-6">
        <div className="flex items-center justify-between gap-3 text-[10px] uppercase tracking-[0.26em] text-muted-foreground/80">
          <span className="flex items-center gap-2">
            <span className="num text-primary">{bundle.symbol}</span>
            <span className="text-muted-foreground/50">·</span>
            <span>{info?.market ?? "—"}</span>
          </span>
          <span className="hidden sm:inline">{today}</span>
        </div>
        <div className="ruler" />

        <div className="grid gap-8 md:grid-cols-[1.4fr_1fr] md:items-end">
          <div className="min-w-0">
            <h1 className="num display text-[clamp(3rem,10vw,7rem)] font-light leading-[0.88] tracking-tighter text-foreground">
              {bundle.symbol}
            </h1>
            <p className="display mt-2 text-lg italic leading-snug tracking-tight text-muted-foreground md:text-2xl">
              {info?.name ?? bundle.symbol}
            </p>
            <div className="mt-4 flex flex-wrap items-center gap-x-4 gap-y-2 text-[11px] uppercase tracking-[0.2em] text-muted-foreground/80">
              {info?.sector && (
                <span className="rounded-sm border hairline bg-muted/30 px-2 py-1">
                  {info.sector}
                </span>
              )}
              {info?.industry && (
                <span className="rounded-sm border hairline bg-muted/30 px-2 py-1">
                  {info.industry}
                </span>
              )}
              {bundle.briefing && <SignalBadge signal={bundle.briefing.overall_signal} size="md" />}
            </div>
          </div>

          <div className="flex flex-col items-stretch gap-3 md:items-end">
            <div className="text-right">
              <div className="text-[10px] uppercase tracking-[0.22em] text-muted-foreground/80">
                Last close
              </div>
              <div className="num mt-1.5 text-4xl font-semibold leading-none tracking-tight md:text-5xl">
                {fmtCurrency(latestPrice, currency)}
              </div>
              {changePct != null && (
                <div
                  className={cn(
                    "num mt-2 text-sm",
                    up ? "text-emerald-400" : "text-rose-400",
                  )}
                >
                  {up ? "▲" : "▼"} {fmtSignedPercent(changePct)}{" "}
                  <span className="text-muted-foreground/70">vs previous</span>
                </div>
              )}
            </div>
            {bundle.briefing && (
              <div className="ml-auto mt-1 rounded-sm border hairline bg-muted/20 px-3 py-2">
                <div className="text-[10px] uppercase tracking-[0.22em] text-muted-foreground/80">
                  Conviction
                </div>
                <div
                  className={cn(
                    "num mt-0.5 text-lg font-semibold tracking-tight",
                    bundle.briefing.conviction.score > 0.15
                      ? "text-emerald-300"
                      : bundle.briefing.conviction.score < -0.15
                        ? "text-rose-300"
                        : "text-foreground",
                  )}
                >
                  {bundle.briefing.conviction.score >= 0 ? "+" : ""}
                  {bundle.briefing.conviction.score.toFixed(2)}
                </div>
              </div>
            )}
          </div>
        </div>
      </header>

      {/* Table of contents */}
      {sections.length > 1 && (
        <nav
          aria-label="Sections on this page"
          className="sticky top-14 z-20 -mx-5 border-y hairline bg-background/80 px-5 py-2.5 backdrop-blur-xl md:-mx-10 md:px-10"
        >
          <div className="flex items-center gap-1 overflow-x-auto">
            <span className="mr-3 shrink-0 text-[10px] uppercase tracking-[0.24em] text-primary">
              Contents
            </span>
            {sections.map((s) => (
              <a
                key={s.id}
                href={`#${s.id}`}
                className="group inline-flex shrink-0 items-center gap-2 rounded-sm px-2.5 py-1 text-xs transition-colors hover:bg-muted/50"
              >
                <span className="num text-[10px] uppercase tracking-[0.2em] text-muted-foreground/70 group-hover:text-primary">
                  {s.num}
                </span>
                <span className="text-muted-foreground group-hover:text-foreground">
                  {s.label}
                </span>
              </a>
            ))}
          </div>
        </nav>
      )}

      <div className="space-y-14">
        {bundle.priceHistory.length > 0 && (
          <SectionCard
            id="chart"
            chapter="01"
            title="Price tape"
            description="Daily close · volume not shown"
          >
            <PriceChart data={bundle.priceHistory} currency={currency} />
          </SectionCard>
        )}

        {bundle.briefing && <BriefingSection data={bundle.briefing} currency={currency} />}
        {bundle.analystReports && <AnalystSection data={bundle.analystReports} />}
        {bundle.debate && <DebateSection data={bundle.debate} />}
        {bundle.fundamentals && <FundamentalsSection data={bundle.fundamentals} />}
        {bundle.technicals && <TechnicalsSection data={bundle.technicals} />}
      </div>
    </div>
  );
}
