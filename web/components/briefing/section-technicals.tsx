import { Check, X } from "lucide-react";
import { SectionCard } from "@/components/shared/section-card";
import { Stat } from "@/components/shared/stat";
import { fmtNumber, fmtPercent } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { Technicals } from "@/lib/types";

export function TechnicalsSection({ data }: { data: Technicals }) {
  const rsi = data.rsi_14;
  const rsiStatus =
    rsi >= 70
      ? { label: "Overbought", cls: "text-rose-600" }
      : rsi <= 30
        ? { label: "Oversold", cls: "text-emerald-600" }
        : { label: "Neutral", cls: "text-muted-foreground" };

  return (
    <SectionCard id="technicals" title="Technicals" description={`As of ${data.as_of_date}`}>
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Stat
          label="RSI (14)"
          value={fmtNumber(rsi, 1)}
          hint={<span className={rsiStatus.cls}>{rsiStatus.label}</span>}
        />
        <Stat
          label="MACD Histogram"
          value={fmtNumber(data.macd_histogram, 2)}
          accent={data.macd_histogram >= 0 ? "up" : "down"}
        />
        <Stat label="ATR (14)" value={fmtNumber(data.atr_14, 2)} hint="Daily volatility" />
        <Stat
          label="Volume vs 20d"
          value={`${fmtNumber(data.volume_ratio, 2)}×`}
          hint={
            data.volume_ratio > 1.2
              ? "Elevated"
              : data.volume_ratio < 0.8
                ? "Light"
                : "Normal"
          }
        />
      </div>

      <div className="mt-5 grid gap-4 md:grid-cols-2">
        <div className="rounded-lg border bg-background p-4">
          <h3 className="mb-3 text-[11px] font-medium text-muted-foreground">
            Moving Averages
          </h3>
          <MaRow label="SMA 20" value={data.sma_20} above={data.above_sma_20} />
          <MaRow label="SMA 50" value={data.sma_50} above={data.above_sma_50} />
          <MaRow label="SMA 200" value={data.sma_200} above={data.above_sma_200} />
          <MaRow label="EMA 20" value={data.ema_20} />
        </div>
        <div className="rounded-lg border bg-background p-4">
          <h3 className="mb-3 text-[11px] font-medium text-muted-foreground">
            52-Week Range
          </h3>
          <div className="space-y-2 text-sm">
            <Row label="High" value={fmtNumber(data.high_52w)} />
            <Row label="Low" value={fmtNumber(data.low_52w)} />
            <Row
              label="From high"
              value={
                <span className="text-rose-600">
                  {fmtPercent(data.pct_from_52w_high, 2, true)}
                </span>
              }
            />
            <Row
              label="From low"
              value={
                <span className="text-emerald-600">
                  {fmtPercent(data.pct_from_52w_low, 2, true)}
                </span>
              }
            />
            <RangeBar low={data.low_52w} high={data.high_52w} current={data.close} />
          </div>
        </div>
      </div>
    </SectionCard>
  );
}

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-baseline justify-between">
      <span className="text-[11px] text-muted-foreground">{label}</span>
      <span className="num text-sm font-medium text-foreground">{value}</span>
    </div>
  );
}

function MaRow({ label, value, above }: { label: string; value: number; above?: boolean }) {
  return (
    <div className="flex items-center justify-between border-b py-2 text-sm last:border-none">
      <div className="flex items-center gap-2">
        {above != null ? (
          above ? (
            <Check className="size-3.5 text-emerald-600" />
          ) : (
            <X className="size-3.5 text-rose-600" />
          )
        ) : (
          <span className="size-3.5" />
        )}
        <span className="text-xs text-muted-foreground">{label}</span>
      </div>
      <span className={cn("num text-sm font-medium text-foreground")}>
        {fmtNumber(value, 2)}
      </span>
    </div>
  );
}

function RangeBar({ low, high, current }: { low: number; high: number; current: number }) {
  const pct = ((current - low) / (high - low)) * 100;
  return (
    <div className="mt-3">
      <div className="relative h-1.5 w-full rounded-full bg-muted">
        <div
          className="absolute top-0 h-full rounded-full bg-gradient-to-r from-rose-500/50 via-amber-400/50 to-emerald-500/50"
          style={{ width: "100%" }}
        />
        <div
          className="absolute top-1/2 size-3 -translate-x-1/2 -translate-y-1/2 rounded-full bg-foreground ring-2 ring-background"
          style={{ left: `${Math.max(0, Math.min(100, pct))}%` }}
        />
      </div>
      <div className="mt-1.5 flex justify-between text-[10px] text-muted-foreground">
        <span>Low</span>
        <span className="num text-foreground">{fmtNumber(current, 2)}</span>
        <span>High</span>
      </div>
    </div>
  );
}
