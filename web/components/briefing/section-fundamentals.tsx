import { SectionCard } from "@/components/shared/section-card";
import { Stat } from "@/components/shared/stat";
import { fmtCompact, fmtNumber, fmtPercent } from "@/lib/format";
import type { Fundamentals } from "@/lib/types";

export function FundamentalsSection({ data }: { data: Fundamentals }) {
  const { info, financials, analyst_recommendations } = data;
  const latestRec = analyst_recommendations?.[0];
  const recTotal = latestRec
    ? latestRec.strongBuy + latestRec.buy + latestRec.hold + latestRec.sell + latestRec.strongSell
    : 0;

  return (
    <SectionCard
      id="fundamentals"
      title="Fundamentals"
      description="Financial profile and analyst consensus"
    >
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Stat label="Market Cap" value={fmtCompact(info.market_cap, info.currency)} />
        <Stat label="P/E (TTM)" value={fmtNumber(info.pe_ratio, 1)} />
        <Stat label="Forward P/E" value={fmtNumber(info.forward_pe, 1)} />
        <Stat label="Beta" value={fmtNumber(info.beta, 2)} />
        <Stat
          label="Revenue"
          value={fmtCompact(financials?.revenue, info.currency)}
          hint={
            financials?.net_margin != null
              ? `Net margin ${fmtPercent(financials.net_margin, 1, true)}`
              : undefined
          }
        />
        <Stat label="Net Income" value={fmtCompact(financials?.net_income, info.currency)} />
        <Stat
          label="Free Cash Flow"
          value={fmtCompact(financials?.free_cash_flow, info.currency)}
        />
        <Stat
          label="Dividend Yield"
          value={info.dividend_yield != null ? `${info.dividend_yield.toFixed(2)}%` : "—"}
        />
      </div>

      {latestRec && recTotal > 0 && (
        <div className="mt-6">
          <h3 className="eyebrow mb-2.5">
            Street consensus · n = <span className="num">{recTotal}</span>
          </h3>
          <RecBar rec={latestRec} total={recTotal} />
        </div>
      )}
    </SectionCard>
  );
}

/**
 * A diverging bull→bear ramp, the way the street's own consensus strips read:
 * conviction at the ends, graphite for hold. The counts are printed under every
 * segment and the aria-label repeats all five, so the bar is a summary of the
 * numbers rather than the only place they exist.
 */
function RecBar({
  rec,
  total,
}: {
  rec: { strongBuy: number; buy: number; hold: number; sell: number; strongSell: number };
  total: number;
}) {
  const parts = [
    { key: "Strong Buy", count: rec.strongBuy, cls: "bg-bull" },
    { key: "Buy", count: rec.buy, cls: "bg-bull/60" },
    { key: "Hold", count: rec.hold, cls: "bg-graphite/40" },
    { key: "Sell", count: rec.sell, cls: "bg-bear/60" },
    { key: "Strong Sell", count: rec.strongSell, cls: "bg-bear" },
  ];
  const summary = parts.map((p) => `${p.key} ${p.count}`).join(", ");

  return (
    <div>
      <div
        className="flex h-2 w-full overflow-hidden rounded-full bg-muted"
        role="img"
        aria-label={`Street consensus across ${total} analysts: ${summary}.`}
      >
        {parts.map((p) => (
          <div
            key={p.key}
            className={p.cls}
            style={{ width: `${(p.count / total) * 100}%` }}
            aria-hidden
          />
        ))}
      </div>
      <div className="mt-3 grid grid-cols-5 gap-2">
        {parts.map((p) => (
          <div key={p.key} className="flex flex-col items-center gap-0.5 text-center">
            <span className="num text-xs font-semibold text-ink">{p.count}</span>
            <span className="text-mini text-graphite">{p.key}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
