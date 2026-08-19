"use client";

import { useRouter } from "next/navigation";
import {
  CartesianGrid,
  ReferenceLine,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { isStale } from "@/lib/screener";
import { signalDirection } from "@/lib/conviction";
import { signalLabel } from "@/lib/format";
import { signalGlyph } from "@/lib/signal-display";
import type { TickerSummary } from "@/lib/types";
import { cn } from "@/lib/utils";

type MapPoint = {
  symbol: string;
  conviction: number;
  convergence: number;
  signal: NonNullable<TickerSummary["signal"]>;
  briefingAgeDays: number | null;
};

const GROUPS = [
  { key: "bull", label: "Buy", fill: "hsl(var(--bull))" },
  { key: "neutral", label: "Hold", fill: "hsl(var(--neutral-signal))" },
  { key: "bear", label: "Sell", fill: "hsl(var(--bear))" },
] as const;

export function ConvictionMap({ tickers }: { tickers: TickerSummary[] }) {
  const router = useRouter();
  const points: MapPoint[] = tickers
    .filter(
      (ticker): ticker is TickerSummary & {
        conviction: number;
        convergence: number;
        signal: NonNullable<TickerSummary["signal"]>;
      } =>
        ticker.conviction != null &&
        ticker.convergence != null &&
        ticker.signal != null,
    )
    .map((ticker) => ({
      symbol: ticker.symbol,
      conviction: Math.max(-1, Math.min(1, ticker.conviction)),
      convergence: Math.max(0, Math.min(1, ticker.convergence)),
      signal: ticker.signal,
      briefingAgeDays: ticker.briefingAgeDays,
    }));

  if (points.length === 0) return null;

  const byDirection = (direction: "bull" | "neutral" | "bear") =>
    points.filter((point) => signalDirection(point.signal) === direction);

  function openTicker(entry: unknown) {
    if (!entry || typeof entry !== "object") return;
    const symbol = (entry as Partial<MapPoint>).symbol;
    if (symbol) router.push(`/${symbol}`);
  }

  return (
    <section
      aria-labelledby="signal-landscape-title"
      className="rounded-lg border bg-card p-4 md:p-5"
    >
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <div>
          <h2 id="signal-landscape-title" className="text-sm font-semibold text-ink">
            Signal landscape
          </h2>
          <p className="mt-1 text-micro text-graphite">
            Conviction × convergence · {points.length} briefed tickers
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-micro text-graphite">
          {GROUPS.map((group) => (
            <span key={group.key} className="inline-flex items-center gap-1.5">
              <span
                className="size-2 rounded-full"
                style={{ backgroundColor: group.fill }}
                aria-hidden
              />
              {group.label}
            </span>
          ))}
          <span className="text-halt">° stale</span>
        </div>
      </div>

      <div className="mt-4 h-[280px]" role="img" aria-label={describeMap(points)}>
        <ResponsiveContainer width="100%" height="100%">
          <ScatterChart margin={{ top: 10, right: 16, bottom: 28, left: 12 }}>
            <CartesianGrid stroke="hsl(var(--rule))" strokeDasharray="2 4" />
            <ReferenceLine
              x={0}
              stroke="hsl(var(--graphite))"
              strokeOpacity={0.45}
              strokeDasharray="3 3"
            />
            <ReferenceLine
              y={0.5}
              stroke="hsl(var(--halt))"
              strokeOpacity={0.55}
              strokeDasharray="3 3"
            />
            <XAxis
              type="number"
              dataKey="conviction"
              domain={[-1, 1]}
              ticks={[-1, -0.5, 0, 0.5, 1]}
              tickFormatter={(value) => `${value > 0 ? "+" : ""}${value}`}
              tick={{ fill: "hsl(var(--graphite))", fontSize: 11 }}
              tickLine={false}
              axisLine={{ stroke: "hsl(var(--rule))" }}
              label={{
                value: "conviction · sell ← → buy",
                position: "insideBottom",
                offset: -16,
                fill: "hsl(var(--graphite))",
                fontSize: 11,
              }}
            />
            <YAxis
              type="number"
              dataKey="convergence"
              domain={[0, 1]}
              ticks={[0, 0.5, 1]}
              tickFormatter={(value) => `${Math.round(value * 100)}%`}
              tick={{ fill: "hsl(var(--graphite))", fontSize: 11 }}
              tickLine={false}
              axisLine={{ stroke: "hsl(var(--rule))" }}
              width={42}
              label={{
                value: "agreement",
                angle: -90,
                position: "insideLeft",
                fill: "hsl(var(--graphite))",
                fontSize: 11,
              }}
            />
            <Tooltip
              cursor={{ stroke: "hsl(var(--graphite))", strokeDasharray: "3 3" }}
              content={<MapTooltip />}
            />
            {GROUPS.map((group) => (
              <Scatter
                key={group.key}
                name={group.label}
                data={byDirection(group.key as "bull" | "neutral" | "bear")}
                fill={group.fill}
                onClick={openTicker}
                cursor="pointer"
              />
            ))}
          </ScatterChart>
        </ResponsiveContainer>
      </div>

      <p className="mt-1 text-micro text-graphite">
        Higher agreement means the four desks are closer together. Stale status is
        a freshness caveat, not a signal.
      </p>

      <ul className="sr-only">
        {points.map((point) => (
          <li key={point.symbol}>
            <a href={`/${point.symbol}`}>
              {point.symbol}: {signalGlyph(point.signal)} {signalLabel(point.signal)}, conviction{" "}
              {point.conviction.toFixed(2)}, convergence {Math.round(point.convergence * 100)}%
              {isStale(point) ? ", stale briefing" : ""}
            </a>
          </li>
        ))}
      </ul>
    </section>
  );
}

function describeMap(points: MapPoint[]) {
  const stale = points.filter((point) => isStale(point)).length;
  return `Signal landscape with ${points.length} briefed tickers. Horizontal axis is conviction from negative sell to positive buy. Vertical axis is convergence from zero to one. ${stale} briefings are stale.`;
}

function MapTooltip({
  active,
  payload,
}: {
  active?: boolean;
  payload?: Array<{ payload?: MapPoint }>;
}) {
  if (!active || !payload?.length) return null;
  const point = payload[0]?.payload;
  if (!point) return null;

  const direction = signalDirection(point.signal);
  return (
    <div className="rounded-lg border bg-popover px-3 py-2 text-xs shadow-lg">
      <div className="flex items-center gap-2">
        <span
          className={cn(
            "font-semibold",
            direction === "bull"
              ? "text-bull"
              : direction === "bear"
                ? "text-bear"
                : "text-graphite",
          )}
        >
          {point.symbol}
        </span>
        <span className="text-graphite">{signalLabel(point.signal)}</span>
      </div>
      <div className="num mt-1 space-y-0.5 text-micro text-graphite">
        <div>Conviction {point.conviction >= 0 ? "+" : ""}{point.conviction.toFixed(2)}</div>
        <div>Convergence {Math.round(point.convergence * 100)}%</div>
        {isStale(point) && <div className="text-halt">Stale briefing</div>}
      </div>
    </div>
  );
}
