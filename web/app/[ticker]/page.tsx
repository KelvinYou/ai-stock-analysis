import { notFound } from "next/navigation";
import { PriceChart } from "@/components/chart/price-chart";
import { DecisionCard } from "@/components/briefing/decision-card";
import { AnalystSection } from "@/components/briefing/section-analysts";
import { BriefingSection } from "@/components/briefing/section-briefing";
import { DebateSection } from "@/components/briefing/section-debate";
import { FundamentalsSection } from "@/components/briefing/section-fundamentals";
import { TechnicalsSection } from "@/components/briefing/section-technicals";
import { SectionCard } from "@/components/shared/section-card";
import { ShareButton } from "@/components/share/share-button";
import { StarButton } from "@/components/ticker-list/star-button";
import { listTickers, loadTicker } from "@/lib/data";
import { describeConviction } from "@/lib/conviction";
import { clampText, fmtCurrency, fmtSignedPercent } from "@/lib/format";
import { buildShareText } from "@/lib/share/text";
import { tickerUrl } from "@/lib/site";
import type { Metadata } from "next";

export const revalidate = 60;
export const dynamicParams = true;

export async function generateStaticParams() {
  const tickers = await listTickers();
  return tickers.map((ticker) => ({ ticker }));
}

/**
 * The unfurl's words. The picture is `opengraph-image.tsx` in this same folder,
 * which Next attaches to both `og:image` and `twitter:image` on its own.
 */
export async function generateMetadata({
  params,
}: {
  params: Promise<{ ticker: string }>;
}): Promise<Metadata> {
  const { ticker } = await params;
  const bundle = await loadTicker(ticker);
  if (!bundle) return {};

  const name = bundle.fundamentals?.info.name;
  const title = name ? `${bundle.symbol} · ${name}` : bundle.symbol;
  // Scrapers cut a description wherever they please; ending the sentence first
  // is the only way to control where.
  const description = bundle.briefing
    ? clampText(
        `${describeConviction(bundle.briefing).phrase}. ${bundle.briefing.executive_summary ?? ""}`,
        200,
      )
    : `Price and fundamentals for ${bundle.symbol}. The analyst desks have not run yet.`;

  return {
    title,
    description,
    openGraph: { title, description, type: "article" },
    twitter: { card: "summary_large_image", title, description },
  };
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

  // Ordered by the pipeline's own evidence chain — the tape, then the desks
  // that read it, then the debate, then the synthesis that settled it. The
  // verdict itself sits above this, because that is what you came for.
  const sections: { id: string; label: string; show: boolean }[] = [
    { id: "chart", label: "Price", show: bundle.priceHistory.length > 0 },
    { id: "fundamentals", label: "Fundamentals", show: !!bundle.fundamentals },
    { id: "technicals", label: "Technicals", show: !!bundle.technicals },
    { id: "analysts", label: "Desks", show: !!bundle.analystReports },
    { id: "debate", label: "Debate", show: !!bundle.debate },
    { id: "briefing", label: "Synthesis", show: !!bundle.briefing },
  ].filter((s) => s.show);

  return (
    <div className="space-y-8">
      <header className="fade-up space-y-6">
        <div className="flex flex-wrap items-start justify-between gap-x-8 gap-y-4">
          <div className="min-w-0">
            <div className="flex items-center gap-2.5">
              <h1 className="text-3xl font-semibold tracking-[-0.03em] text-ink [font-stretch:125%] md:text-4xl">
                {bundle.symbol}
              </h1>
              <StarButton symbol={bundle.symbol} />
              {info?.market && (
                <span className="text-micro font-semibold uppercase tracking-[0.09em] text-graphite">
                  {info.market}
                </span>
              )}
              <ShareButton
                symbol={bundle.symbol}
                shareText={buildShareText(bundle, tickerUrl(bundle.symbol))}
                className="ml-1"
              />
            </div>
            <p className="mt-1.5 truncate text-sm text-graphite">
              {info?.name ?? bundle.symbol}
            </p>
            {(info?.sector || info?.industry) && (
              <p className="mt-2 text-micro uppercase tracking-[0.07em] text-graphite">
                {[info?.sector, info?.industry].filter(Boolean).join(" · ")}
              </p>
            )}
          </div>

          <div className="text-right">
            <div className="eyebrow">Last close</div>
            <div className="num mt-1.5 text-3xl font-medium text-ink md:text-4xl">
              {fmtCurrency(latestPrice, currency)}
            </div>
            {changePct != null && (
              // Colour and glyph together — the arrow keeps the meaning legible
              // without hue, the hue makes it readable at a glance.
              <div className="num mt-1 text-xs text-graphite">
                <span className={up ? "text-bull" : "text-bear"}>
                  <span aria-hidden>{up ? "▲" : "▼"}</span>{" "}
                  {fmtSignedPercent(changePct)}
                </span>{" "}
                vs previous
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
          className="sticky top-topbar z-20 -mx-5 border-b bg-paper/85 px-5 py-2.5 backdrop-blur-md md:-mx-10 md:px-10"
        >
          <div className="flex items-center gap-5 overflow-x-auto">
            {sections.map((s) => (
              <a
                key={s.id}
                href={`#${s.id}`}
                className="shrink-0 border-b-2 border-transparent pb-0.5 text-micro font-semibold uppercase tracking-[0.07em] text-graphite transition-colors hover:border-ink hover:text-ink"
              >
                {s.label}
              </a>
            ))}
          </div>
        </nav>
      )}

      <div className="space-y-14">
        {(bundle.priceHistory.length > 0 || bundle.fundamentals || bundle.technicals) && (
          <div className="space-y-6">
            <p className="eyebrow border-t-2 border-ink pt-4">Layer 1 · The tape</p>
            {bundle.priceHistory.length > 0 && (
              <SectionCard id="chart" title="Price" description="Daily close">
                <PriceChart
                  data={bundle.priceHistory}
                  currency={currency}
                  technicals={bundle.technicals}
                  supportLevels={bundle.analystReports?.technical.support_levels}
                  resistanceLevels={bundle.analystReports?.technical.resistance_levels}
                  actionPlan={bundle.briefing?.action_plan}
                />
              </SectionCard>
            )}
            {bundle.fundamentals && <FundamentalsSection data={bundle.fundamentals} />}
            {bundle.technicals && <TechnicalsSection data={bundle.technicals} />}
          </div>
        )}

        {bundle.analystReports && <AnalystSection data={bundle.analystReports} />}
        {bundle.debate && (
          <DebateSection data={bundle.debate} verdict={bundle.briefing?.research_verdict} />
        )}
        {bundle.briefing && <BriefingSection data={bundle.briefing} currency={currency} />}
      </div>
    </div>
  );
}
