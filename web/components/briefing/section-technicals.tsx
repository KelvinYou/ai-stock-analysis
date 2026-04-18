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
      ? { label: "Overbought", cls: "text-rose-400" }
      : rsi <= 30
        ? { label: "Oversold", cls: "text-emerald-400" }
        : { label: "Neutral", cls: "text-muted-foreground" };

  return (
    <SectionCard
      id="technicals"
      chapter="06"
      title="Technicals"
      description={`As of ${data.as_of_date}`}
    >
      <div className="grid grid-cols-2 gap-px overflow-hidden rounded-sm border hairline bg-border/40 md:grid-cols-4">
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
        <Stat
          label="ATR (14)"
          value={fmtNumber(data.atr_14, 2)}
          hint="Daily volatility"
        />
        <Stat
          label="Volume vs 20d"
          value={`${fmtNumber(data.volume_ratio, 2)}×`}
          hint={data.volume_ratio > 1.2 ? "Elevated" : data.volume_ratio < 0.8 ? "Light" : "Normal"}
        />
      </div>

      <div className="mt-6 grid gap-5 md:grid-cols-2">
        <div className="rounded-sm border hairline bg-muted/10 p-5">
          <h3 className="mb-4 text-[10px] uppercase tracking-[0.22em] text-muted-foreground/80">
            Moving Averages
          </h3>
          <MaRow label="SMA 20" value={data.sma_20} above={data.above_sma_20} />
          <MaRow label="SMA 50" value={data.sma_50} above={data.above_sma_50} />
          <MaRow label="SMA 200" value={data.sma_200} above={data.above_sma_200} />
          <MaRow label="EMA 20" value={data.ema_20} />
        </div>
        <div className="rounded-sm border hairline bg-muted/10 p-5">
          <h3 className="mb-4 text-[10px] uppercase tracking-[0.22em] text-muted-foreground/80">
            52-Week Range
          </h3>
          <div className="space-y-2.5 text-sm">
            <Row label="High" value={fmtNumber(data.high_52w)} />
            <Row label="Low" value={fmtNumber(data.low_52w)} />
            <Row
              label="From high"
              value={
                <span className="text-rose-400">
                  {fmtPercent(data.pct_from_52w_high, 2, true)}
                </span>
              }
            />
            <Row
              label="From low"
              value={
                <span className="text-emerald-400">
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
      <span className="text-[10px] uppercase tracking-[0.22em] text-muted-foreground/80">
        {label}
      </span>
      <span className="num font-medium">{value}</span>
    </div>
  );
}

function MaRow({ label, value, above }: { label: string; value: number; above?: boolean }) {
  return (
    <div className="flex items-center justify-between border-b hairline py-2 text-sm last:border-none">
      <div className="flex items-center gap-2">
        {above != null ? (
          above ? (
            <Check className="size-3.5 text-emerald-400" />
          ) : (
            <X className="size-3.5 text-rose-400" />
          )
        ) : (
          <span className="size-3.5" />
        )}
        <span className="text-[11px] uppercase tracking-[0.18em] text-muted-foreground">
          {label}
        </span>
      </div>
      <span className={cn("num font-medium")}>{fmtNumber(value, 2)}</span>
    </div>
  );
}

function RangeBar({ low, high, current }: { low: number; high: number; current: number }) {
  const pct = ((current - low) / (high - low)) * 100;
  return (
    <div className="mt-4">
      <div className="relative h-1.5 w-full rounded-full bg-muted">
        <div
          className="absolute top-0 h-full rounded-full bg-gradient-to-r from-rose-500/60 via-amber-400/60 to-emerald-500/60"
          style={{ width: "100%" }}
        />
        <div
          className="absolute top-1/2 size-3 -translate-x-1/2 -translate-y-1/2 rounded-full bg-foreground ring-2 ring-background"
          style={{ left: `${Math.max(0, Math.min(100, pct))}%` }}
        />
      </div>
      <div className="mt-1.5 flex justify-between text-[9px] uppercase tracking-[0.18em] text-muted-foreground/70">
        <span>Low</span>
        <span className="num text-foreground/80">{fmtNumber(current, 2)}</span>
        <span>High</span>
      </div>
    </div>
  );
}
