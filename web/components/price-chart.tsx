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

  const stroke = up ? "hsl(152 70% 48%)" : "hsl(0 70% 56%)";
  const gradientId = React.useId();

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-baseline justify-between gap-3">
        <div>
          <div className="text-3xl font-semibold num tracking-tight">
            {fmtCurrency(last, currency)}
          </div>
          <div className={cn("num text-sm", up ? "text-emerald-400" : "text-rose-400")}>
            {up ? "▲" : "▼"} {fmtCurrency(Math.abs(change), currency)} · {fmtSignedPercent(changePct)}
            <span className="ml-1 text-muted-foreground">· {range}</span>
          </div>
        </div>
        <div className="inline-flex rounded-lg bg-muted/60 p-0.5">
          {RANGES.map((r) => (
            <button
              key={r.key}
              onClick={() => setRange(r.key)}
              className={cn(
                "px-2.5 py-1 text-xs font-medium rounded-md transition-colors",
                range === r.key
                  ? "bg-card text-foreground shadow"
                  : "text-muted-foreground hover:text-foreground",
              )}
            >
              {r.key}
            </button>
          ))}
        </div>
      </div>
      <div className="h-[280px] md:h-[340px]">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={sliced} margin={{ top: 5, right: 8, left: 0, bottom: 0 }}>
            <defs>
              <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={stroke} stopOpacity={0.35} />
                <stop offset="100%" stopColor={stroke} stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid stroke="hsl(var(--border))" strokeOpacity={0.4} vertical={false} />
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
              cursor={{ stroke: "hsl(var(--border))", strokeDasharray: "3 3" }}
              content={<ChartTooltip currency={currency} />}
            />
            <Area
              type="monotone"
              dataKey="close"
              stroke={stroke}
              strokeWidth={2}
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
    <div className="rounded-md border border-border/60 bg-popover/95 px-3 py-2 text-xs shadow-xl backdrop-blur">
      <div className="text-muted-foreground">{fmtDateShort(p.date)}</div>
      <div className="num mt-1 flex items-center gap-3">
        <span>Close</span>
        <span className="font-semibold">{fmtCurrency(p.close, currency)}</span>
      </div>
      <div className="num mt-0.5 flex items-center gap-3 text-muted-foreground">
        <span>Vol</span>
        <span>{p.volume.toLocaleString("en-US")}</span>
      </div>
    </div>
  );
}
