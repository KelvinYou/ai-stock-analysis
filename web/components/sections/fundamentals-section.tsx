import { SectionCard } from "./section-card";
import { Stat } from "@/components/stat";
import { fmtCompact, fmtNumber, fmtPercent } from "@/lib/format";
import type { Fundamentals } from "@/lib/types";

export function FundamentalsSection({ data }: { data: Fundamentals }) {
  const { info, financials, analyst_recommendations } = data;
  const latestRec = analyst_recommendations[0];
  const recTotal = latestRec
    ? latestRec.strongBuy + latestRec.buy + latestRec.hold + latestRec.sell + latestRec.strongSell
    : 0;

  return (
    <SectionCard
      id="fundamentals"
      title="Fundamentals snapshot"
      description="Raw financial profile and analyst consensus"
    >
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Stat label="Market Cap" value={fmtCompact(info.market_cap, info.currency)} />
        <Stat label="P/E (TTM)" value={fmtNumber(info.pe_ratio, 1)} />
        <Stat label="Forward P/E" value={fmtNumber(info.forward_pe, 1)} />
        <Stat label="Beta" value={fmtNumber(info.beta, 2)} />
        <Stat
          label="Revenue"
          value={fmtCompact(financials.revenue, info.currency)}
          hint={
            financials.net_margin != null
              ? `Net margin ${fmtPercent(financials.net_margin, 1, true)}`
              : undefined
          }
        />
        <Stat label="Net Income" value={fmtCompact(financials.net_income, info.currency)} />
        <Stat label="Free Cash Flow" value={fmtCompact(financials.free_cash_flow, info.currency)} />
        <Stat
          label="Dividend Yield"
          value={info.dividend_yield != null ? `${info.dividend_yield.toFixed(2)}%` : "—"}
        />
      </div>

      {latestRec && recTotal > 0 && (
        <div className="mt-6">
          <h3 className="mb-3 text-sm font-medium text-muted-foreground">Analyst consensus</h3>
          <RecBar rec={latestRec} total={recTotal} />
        </div>
      )}
    </SectionCard>
  );
}

function RecBar({
  rec,
  total,
}: {
  rec: { strongBuy: number; buy: number; hold: number; sell: number; strongSell: number };
  total: number;
}) {
  const parts = [
    { key: "Strong Buy", count: rec.strongBuy, cls: "bg-emerald-500" },
    { key: "Buy", count: rec.buy, cls: "bg-emerald-400/80" },
    { key: "Hold", count: rec.hold, cls: "bg-zinc-400/80" },
    { key: "Sell", count: rec.sell, cls: "bg-rose-400/80" },
    { key: "Strong Sell", count: rec.strongSell, cls: "bg-rose-500" },
  ];
  return (
    <div>
      <div className="flex h-2 w-full overflow-hidden rounded-full bg-muted">
        {parts.map((p) => (
          <div
            key={p.key}
            className={p.cls}
            style={{ width: `${(p.count / total) * 100}%` }}
            title={`${p.key}: ${p.count}`}
          />
        ))}
      </div>
      <div className="mt-3 grid grid-cols-5 gap-2 text-[11px]">
        {parts.map((p) => (
          <div key={p.key} className="flex flex-col items-center gap-0.5">
            <span className="num font-semibold">{p.count}</span>
            <span className="text-muted-foreground">{p.key}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
