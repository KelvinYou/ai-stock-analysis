import { Check, X } from "lucide-react";
import { SectionCard } from "@/components/shared/section-card";
import { Stat } from "@/components/shared/stat";
import { fmtNumber, fmtPercent } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { Technicals } from "@/lib/types";

export function TechnicalsSection({ data }: { data: Technicals }) {
  const rsi = data.rsi_14;
  // Weight *and* hue: the medium weight still marks "this is an extreme
  // reading" on its own, and the colour says which way the extreme cuts.
  const rsiStatus =
    rsi >= 70
      ? { label: "Overbought", cls: "font-medium text-bear" }
      : rsi <= 30
        ? { label: "Oversold", cls: "font-medium text-bull" }
        : { label: "Neutral", cls: "text-graphite" };

  const macdUp = data.macd_histogram >= 0;

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
          value={
            <span className={macdUp ? "text-bull" : "text-bear"}>
              <span aria-hidden>{macdUp ? "▲" : "▼"}</span>{" "}
              {macdUp ? "+" : ""}
              {fmtNumber(data.macd_histogram, 2)}
            </span>
          }
          hint={macdUp ? "Above zero" : "Below zero"}
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
          <h3 className="eyebrow mb-3">Moving averages</h3>
          <MaRow label="SMA 20" value={data.sma_20} above={data.above_sma_20} />
          <MaRow label="SMA 50" value={data.sma_50} above={data.above_sma_50} />
          <MaRow label="SMA 200" value={data.sma_200} above={data.above_sma_200} />
          <MaRow label="EMA 20" value={data.ema_20} />
        </div>
        <div className="rounded-lg border bg-background p-4">
          <h3 className="eyebrow mb-3">52-week range</h3>
          <div className="space-y-2">
            <Row label="High" value={fmtNumber(data.high_52w)} />
            <Row label="Low" value={fmtNumber(data.low_52w)} />
            <Row
              label="From high"
              value={
                <span className="text-bear">
                  <span aria-hidden>▼</span>{" "}
                  {fmtPercent(data.pct_from_52w_high, 2, true)}
                </span>
              }
            />
            <Row
              label="From low"
              value={
                <span className="text-bull">
                  <span aria-hidden>▲</span>{" "}
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
    <div className="flex items-baseline justify-between gap-3">
      <span className="text-micro text-graphite">{label}</span>
      <span className="num text-sm font-medium text-ink">{value}</span>
    </div>
  );
}

function MaRow({ label, value, above }: { label: string; value: number; above?: boolean }) {
  return (
    <div className="flex items-center justify-between border-b py-2 last:border-none">
      <div className="flex items-center gap-2">
        {above != null ? (
          above ? (
            <>
              <Check className="size-3.5 shrink-0 text-bull" aria-hidden />
              <span className="sr-only">Price above</span>
            </>
          ) : (
            <>
              <X className="size-3.5 shrink-0 text-bear" aria-hidden />
              <span className="sr-only">Price below</span>
            </>
          )
        ) : (
          <span className="size-3.5" aria-hidden />
        )}
        <span className="text-xs text-graphite">{label}</span>
      </div>
      <span
        className={cn(
          "num text-sm font-medium",
          above === false ? "text-graphite" : "text-ink",
        )}
      >
        {fmtNumber(value, 2)}
      </span>
    </div>
  );
}

/**
 * A diverging track: bear at the 52-week low, neutral graphite through the
 * middle, bull at the high. The knob marks the current close, and the
 * aria-label states the position in words so the ramp is never the only way
 * to read it.
 */
function RangeBar({ low, high, current }: { low: number; high: number; current: number }) {
  const raw = high === low ? 0 : ((current - low) / (high - low)) * 100;
  const pct = Math.max(0, Math.min(100, raw));

  return (
    <div className="mt-3">
      <div
        className="relative h-1.5 w-full overflow-visible rounded-full"
        role="progressbar"
        aria-valuenow={Math.round(pct)}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={`Close ${fmtNumber(current, 2)} sits ${Math.round(pct)}% of the way from the 52-week low ${fmtNumber(low, 2)} to the high ${fmtNumber(high, 2)}.`}
      >
        <div
          className="absolute inset-0 overflow-hidden rounded-full bg-gradient-to-r from-bear via-graphite/30 to-bull"
          aria-hidden
        />
        <div
          className="absolute top-1/2 size-3 -translate-x-1/2 -translate-y-1/2 rounded-full bg-ink ring-2 ring-background"
          style={{ left: `${pct}%` }}
          aria-hidden
        />
      </div>
      <div className="mt-1.5 flex justify-between text-mini text-graphite">
        <span>Low</span>
        <span className="num text-ink">{fmtNumber(current, 2)}</span>
        <span>High</span>
      </div>
    </div>
  );
}
