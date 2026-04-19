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

  const stroke = up ? "rgb(5 150 105)" : "rgb(225 29 72)";
  const gradientId = React.useId();

  return (
    <div>
      <div className="mb-5 flex flex-wrap items-end justify-between gap-4">
        <div>
          <div className="text-[11px] font-medium text-muted-foreground">
            {range} range
          </div>
          <div className="mt-1 flex items-baseline gap-2.5">
            <span className="num text-2xl font-semibold tracking-tight text-foreground md:text-3xl">
              {fmtCurrency(last, currency)}
            </span>
            <span
              className={cn(
                "num text-xs font-medium",
                up ? "text-emerald-600" : "text-rose-600",
              )}
            >
              {up ? "+" : ""}
              {fmtCurrency(change, currency)} · {fmtSignedPercent(changePct)}
            </span>
          </div>
        </div>
        <div className="inline-flex items-stretch overflow-hidden rounded-lg border bg-muted/40 p-0.5">
          {RANGES.map((r) => (
            <button
              key={r.key}
              onClick={() => setRange(r.key)}
              className={cn(
                "num rounded-md px-2.5 py-1 text-[11px] font-medium transition-colors",
                range === r.key
                  ? "bg-background text-foreground shadow-sm"
                  : "text-muted-foreground hover:text-foreground",
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
                <stop offset="0%" stopColor={stroke} stopOpacity={0.22} />
                <stop offset="100%" stopColor={stroke} stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid stroke="hsl(var(--border))" strokeOpacity={0.6} vertical={false} />
            <XAxis
              dataKey="date"
              tickFormatter={fmtDateShort}
              stroke="hsl(var(--muted-foreground))"
              tickLine={false}
              axisLine={false}
              minTickGap={32}
              fontSize={11}
            />
            <YAxis
              domain={["auto", "auto"]}
              stroke="hsl(var(--muted-foreground))"
              tickLine={false}
              axisLine={false}
              tickFormatter={(v) => fmtCurrency(v, currency).replace(/\.\d+$/, "")}
              width={60}
              fontSize={11}
            />
            <Tooltip
              cursor={{ stroke: "hsl(var(--foreground))", strokeOpacity: 0.3, strokeDasharray: "3 3" }}
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
      <div className="text-[11px] font-medium text-muted-foreground">
        {fmtDateShort(p.date)}
      </div>
      <div className="num mt-1 flex items-center gap-3">
        <span className="text-muted-foreground">Close</span>
        <span className="font-semibold text-foreground">{fmtCurrency(p.close, currency)}</span>
      </div>
      <div className="num mt-0.5 flex items-center gap-3 text-muted-foreground">
        <span>Vol</span>
        <span>{p.volume.toLocaleString("en-US")}</span>
      </div>
    </div>
  );
}
