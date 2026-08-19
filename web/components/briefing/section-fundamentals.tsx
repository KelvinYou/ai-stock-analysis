import type { ReactNode } from "react";
import { SectionCard } from "@/components/shared/section-card";
import { Stat } from "@/components/shared/stat";
import { fmtCompact, fmtNumber, fmtPercent } from "@/lib/format";
import { cn } from "@/lib/utils";
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

      {financials && <FundamentalsVisuals info={info} financials={financials} />}

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

function FundamentalsVisuals({
  info,
  financials,
}: {
  info: Fundamentals["info"];
  financials: NonNullable<Fundamentals["financials"]>;
}) {
  const valuation = [info.pe_ratio, info.forward_pe].filter(
    (value): value is number => value != null && Number.isFinite(value) && value > 0,
  );
  const margins = [
    { label: "Gross", value: financials.gross_margin },
    { label: "Operating", value: financials.operating_margin },
    { label: "Net", value: financials.net_margin },
  ].filter((item): item is { label: string; value: number } =>
    item.value != null && Number.isFinite(item.value),
  );
  const balance = [
    { label: "Free cash flow", value: financials.free_cash_flow },
    { label: "Total debt", value: financials.total_debt },
  ].filter((item): item is { label: string; value: number } =>
    item.value != null && Number.isFinite(item.value),
  );

  return (
    <div className="mt-6 grid gap-4 md:grid-cols-3">
      <SnapshotBlock title="Valuation snapshot">
        {valuation.length > 0 ? (
          <div className="space-y-3" role="img" aria-label={valuationLabel(info)}>
            <ScaledBar label="P/E" value={info.pe_ratio} max={Math.max(...valuation)} />
            <ScaledBar label="Forward P/E" value={info.forward_pe} max={Math.max(...valuation)} />
          </div>
        ) : (
          <p className="text-sm text-graphite">No positive P/E values reported</p>
        )}
      </SnapshotBlock>

      <SnapshotBlock title="Margin profile">
        {margins.length > 0 ? (
          <div className="space-y-3" role="img" aria-label={marginLabel(margins)}>
            {margins.map((item) => (
              <MarginBar key={item.label} label={item.label} value={item.value} />
            ))}
          </div>
        ) : (
          <p className="text-sm text-graphite">No margin data reported</p>
        )}
      </SnapshotBlock>

      <SnapshotBlock title="Cash flow vs debt">
        {balance.length > 0 ? (
          <div className="space-y-3" role="img" aria-label={balanceLabel(balance, info.currency)}>
            <BalanceBar items={balance} currency={info.currency} />
            {financials.free_cash_flow != null && financials.total_debt != null && financials.total_debt > 0 && (
              <p className="num text-micro text-graphite">
                FCF / debt {fmtNumber(financials.free_cash_flow / financials.total_debt, 2)}×
              </p>
            )}
          </div>
        ) : (
          <p className="text-sm text-graphite">No cash flow or debt data reported</p>
        )}
      </SnapshotBlock>
    </div>
  );
}

function SnapshotBlock({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="rounded-lg border bg-background p-4">
      <h3 className="eyebrow mb-3">{title}</h3>
      {children}
    </div>
  );
}

function ScaledBar({ label, value, max }: { label: string; value: number | null; max: number }) {
  if (value == null || !Number.isFinite(value)) return null;
  const width = max > 0 ? Math.max(4, (value / max) * 100) : 0;
  return (
    <div>
      <div className="flex items-baseline justify-between gap-2">
        <span className="text-xs text-graphite">{label}</span>
        <span className="num text-xs font-medium text-ink">{fmtNumber(value, 1)}×</span>
      </div>
      <div className="mt-1.5 h-2 overflow-hidden rounded-full bg-muted">
        <div className="h-full rounded-full bg-action" style={{ width: `${width}%` }} />
      </div>
    </div>
  );
}

function MarginBar({ label, value }: { label: string; value: number }) {
  const width = Math.min(100, Math.max(4, Math.abs(value) * 100));
  const positive = value >= 0;
  return (
    <div>
      <div className="flex items-baseline justify-between gap-2">
        <span className="text-xs text-graphite">{label}</span>
        <span className={cn("num text-xs font-medium", positive ? "text-bull" : "text-bear")}>
          {fmtPercent(value, 1, true)}
        </span>
      </div>
      <div className="mt-1.5 h-2 overflow-hidden rounded-full bg-muted">
        <div
          className={cn("h-full rounded-full", positive ? "bg-bull" : "bg-bear")}
          style={{ width: `${width}%` }}
        />
      </div>
    </div>
  );
}

function BalanceBar({
  items,
  currency,
}: {
  items: Array<{ label: string; value: number }>;
  currency: string;
}) {
  const max = Math.max(...items.map((item) => Math.abs(item.value)), 1);
  return (
    <div className="space-y-3">
      {items.map((item) => (
        <div key={item.label}>
          <div className="flex items-baseline justify-between gap-2">
            <span className="text-xs text-graphite">{item.label}</span>
            <span className="num text-xs font-medium text-ink">
              {fmtCompact(item.value, currency)}
            </span>
          </div>
          <div className="mt-1.5 h-2 overflow-hidden rounded-full bg-muted">
            <div
              className={cn(
                "h-full rounded-full",
                item.label === "Free cash flow"
                  ? item.value >= 0
                    ? "bg-bull"
                    : "bg-bear"
                  : "bg-graphite",
              )}
              style={{ width: `${Math.max(4, (Math.abs(item.value) / max) * 100)}%` }}
            />
          </div>
        </div>
      ))}
    </div>
  );
}

function valuationLabel(info: Fundamentals["info"]) {
  return `Valuation snapshot. P/E ${info.pe_ratio ?? "unavailable"}. Forward P/E ${info.forward_pe ?? "unavailable"}. Bars are scaled only against each other.`;
}

function marginLabel(margins: Array<{ label: string; value: number }>) {
  return `Margin profile. ${margins.map((item) => `${item.label} ${fmtPercent(item.value, 1, true)}`).join(", ")}.`;
}

function balanceLabel(items: Array<{ label: string; value: number }>, currency: string) {
  return `Cash flow versus debt. ${items.map((item) => `${item.label} ${fmtCompact(item.value, currency)}`).join(", ")}. Bars share a scale.`;
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
