"use client";

import * as React from "react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { PricePoint } from "@/lib/types";
import { cn } from "@/lib/utils";
import { fmtCurrency, fmtDateShort, fmtSignedPercent } from "@/lib/format";

const RANGES = [
  { key: "1M", days: 30 },
  { key: "3M", days: 90 },
  { key: "6M", days: 180 },
  { key: "1Y", days: 365 },
  { key: "ALL", days: Number.POSITIVE_INFINITY },
] as const;

type RangeKey = (typeof RANGES)[number]["key"];

/**
 * Recharts sets axis type through numeric props, so the type scale has to be
 * restated here as a number. 11 is `text-micro` (0.6875rem at a 16px root).
 */
const AXIS_FONT_SIZE = 11;

/**
 * The series carries direction: bull when the selected range closed up, bear
 * when it closed down. Colour is additive here — the delta above the plot still
 * spells the direction out in a ▲/▼ glyph and a signed number, so a
 * colour-blind reader loses nothing.
 */
const seriesColor = (up: boolean) => (up ? "hsl(var(--bull))" : "hsl(var(--bear))");

export function PriceChart({
  data,
  currency = "USD",
}: {
  data: PricePoint[];
  currency?: string;
}) {
  const [range, setRange] = React.useState<RangeKey>("6M");

  const sliced = React.useMemo(() => {
    const cfg = RANGES.find((r) => r.key === range)!;
    if (!Number.isFinite(cfg.days)) return data;
    return data.slice(-cfg.days);
  }, [data, range]);

  const first = sliced[0]?.close ?? 0;
  const last = sliced.at(-1)?.close ?? 0;
  const change = last - first;
  const changePct = first ? (change / first) * 100 : 0;
  const up = change >= 0;
  const stroke = seriesColor(up);

  const gradientId = React.useId();

  return (
    <div>
      <div className="mb-5 flex flex-wrap items-end justify-between gap-4">
        <div>
          <div className="eyebrow">{range} range</div>
          <div className="mt-1 flex items-baseline gap-2.5">
            <span className="num text-2xl font-semibold tracking-tight text-ink md:text-3xl">
              {fmtCurrency(last, currency)}
            </span>
            <span
              className={cn(
                "num flex items-baseline gap-1.5 text-xs font-medium",
                up ? "text-bull" : "text-bear",
              )}
            >
              <span className="text-mini leading-none" aria-hidden>
                {up ? "▲" : "▼"}
              </span>
              <span>
                {up ? "+" : ""}
                {fmtCurrency(change, currency)} · {fmtSignedPercent(changePct)}
              </span>
            </span>
          </div>
        </div>
        <div className="inline-flex items-stretch overflow-hidden rounded-lg border bg-secondary p-0.5">
          {RANGES.map((r) => (
            <button
              key={r.key}
              onClick={() => setRange(r.key)}
              aria-pressed={range === r.key}
              className={cn(
                "num rounded px-2.5 py-1 text-micro font-medium transition-colors",
                range === r.key
                  ? "bg-action text-action-foreground"
                  : "text-graphite hover:text-action",
              )}
            >
              {r.key}
            </button>
          ))}
        </div>
      </div>
      <div className="h-[260px] md:h-[320px]">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={sliced} margin={{ top: 5, right: 8, left: 0, bottom: 0 }}>
            <defs>
              <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={stroke} stopOpacity={0.2} />
                <stop offset="100%" stopColor={stroke} stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid stroke="hsl(var(--rule))" vertical={false} />
            <XAxis
              dataKey="date"
              tickFormatter={fmtDateShort}
              stroke="hsl(var(--rule))"
              tick={{ fill: "hsl(var(--graphite))", fontSize: AXIS_FONT_SIZE }}
              tickLine={false}
              axisLine={false}
              minTickGap={32}
            />
            <YAxis
              domain={["auto", "auto"]}
              stroke="hsl(var(--rule))"
              tick={{ fill: "hsl(var(--graphite))", fontSize: AXIS_FONT_SIZE }}
              tickLine={false}
              axisLine={false}
              tickFormatter={(v) => fmtCurrency(v, currency).replace(/\.\d+$/, "")}
              width={60}
            />
            <Tooltip
              cursor={{ stroke: "hsl(var(--graphite))", strokeDasharray: "3 3" }}
              content={<ChartTooltip currency={currency} />}
            />
            <Area
              type="monotone"
              dataKey="close"
              stroke={stroke}
              strokeWidth={1.75}
              fill={`url(#${gradientId})`}
              isAnimationActive={false}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

function ChartTooltip({
  active,
  payload,
  currency,
}: {
  active?: boolean;
  payload?: Array<{ payload: PricePoint }>;
  currency: string;
}) {
  if (!active || !payload?.length) return null;
  const p = payload[0].payload;
  return (
    <div className="rounded-lg border bg-popover px-3 py-2 text-xs shadow-lg">
      <div className="num text-micro font-medium text-graphite">
        {fmtDateShort(p.date)}
      </div>
      <div className="num mt-1 flex items-center gap-3">
        <span className="text-graphite">Close</span>
        <span className="font-semibold text-ink">{fmtCurrency(p.close, currency)}</span>
      </div>
      <div className="num mt-0.5 flex items-center gap-3 text-graphite">
        <span>Vol</span>
        <span>{p.volume.toLocaleString("en-US")}</span>
      </div>
    </div>
  );
}
