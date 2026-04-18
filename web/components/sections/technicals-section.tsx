import { Check, X } from "lucide-react";
import { SectionCard } from "./section-card";
import { Stat } from "@/components/stat";
import { fmtNumber, fmtPercent } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { Technicals } from "@/lib/types";

export function TechnicalsSection({ data }: { data: Technicals }) {
  const rsi = data.rsi_14;
  const rsiStatus =
    rsi >= 70 ? { label: "Overbought", cls: "text-rose-400" } :
    rsi <= 30 ? { label: "Oversold", cls: "text-emerald-400" } :
    { label: "Neutral", cls: "text-muted-foreground" };

  return (
    <SectionCard
      id="technicals"
      title="Technical indicators"
      description={`As of ${data.as_of_date}`}
    >
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

      <div className="mt-6 grid gap-4 md:grid-cols-2">
        <div className="rounded-lg border border-border/50 bg-muted/20 p-4">
          <h3 className="mb-3 text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
            Moving Averages
          </h3>
          <MaRow label="SMA 20" value={data.sma_20} above={data.above_sma_20} />
          <MaRow label="SMA 50" value={data.sma_50} above={data.above_sma_50} />
          <MaRow label="SMA 200" value={data.sma_200} above={data.above_sma_200} />
          <MaRow label="EMA 20" value={data.ema_20} />
        </div>
        <div className="rounded-lg border border-border/50 bg-muted/20 p-4">
          <h3 className="mb-3 text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
            52-Week Range
          </h3>
          <div className="space-y-2 text-sm">
            <div className="flex justify-between">
              <span className="text-muted-foreground">High</span>
              <span className="num font-medium">{fmtNumber(data.high_52w)}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Low</span>
              <span className="num font-medium">{fmtNumber(data.low_52w)}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">From high</span>
              <span className="num font-medium text-rose-400">
                {fmtPercent(data.pct_from_52w_high, 2, true)}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">From low</span>
              <span className="num font-medium text-emerald-400">
                {fmtPercent(data.pct_from_52w_low, 2, true)}
              </span>
            </div>
            <RangeBar low={data.low_52w} high={data.high_52w} current={data.close} />
          </div>
        </div>
      </div>
    </SectionCard>
  );
}

function MaRow({ label, value, above }: { label: string; value: number; above?: boolean }) {
  return (
    <div className="flex items-center justify-between py-1.5 text-sm">
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
        <span className="text-muted-foreground">{label}</span>
      </div>
      <span className={cn("num font-medium")}>{fmtNumber(value, 2)}</span>
    </div>
  );
}

function RangeBar({ low, high, current }: { low: number; high: number; current: number }) {
  const pct = ((current - low) / (high - low)) * 100;
  return (
    <div className="mt-3">
      <div className="relative h-2 w-full rounded-full bg-muted">
        <div
          className="absolute top-0 h-full rounded-full bg-gradient-to-r from-rose-500/40 via-amber-400/40 to-emerald-500/40"
          style={{ width: "100%" }}
        />
        <div
          className="absolute top-1/2 size-3 -translate-x-1/2 -translate-y-1/2 rounded-full bg-foreground ring-2 ring-background"
          style={{ left: `${Math.max(0, Math.min(100, pct))}%` }}
        />
      </div>
    </div>
  );
}
