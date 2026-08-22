"use client";

import * as React from "react";
import type { ActionPlan } from "@/lib/types";
import { CHART_RANGES } from "@/lib/chart-data";
import type {
  ChartData,
  ChartLatestIndicators,
  ChartPoint,
} from "@/lib/chart-data";
import { cn } from "@/lib/utils";
import { fmtCurrency, fmtDateShort, fmtNumber, fmtSignedPercent } from "@/lib/format";

type RangeKey = (typeof CHART_RANGES)[number]["key"];
type IndicatorKey = Exclude<keyof NonNullable<ChartPoint["indicators"]>, "date">;

type LevelKey = "support" | "resistance" | "entry" | "stop" | "tp1" | "tp2";

type LevelLine = {
  value: number;
  label: string;
  color: string;
  dash?: string;
};

type ReferenceLevel = LevelLine & { key: LevelKey };

const COLORS = {
  bull: "hsl(var(--bull))",
  bear: "hsl(var(--bear))",
  graphite: "hsl(var(--graphite))",
  rule: "hsl(var(--rule))",
  action: "hsl(var(--action))",
  trendFast: "hsl(var(--trend-fast))",
  trendMid: "hsl(var(--trend-mid))",
  trendSlow: "hsl(var(--trend-slow))",
};

const LEVEL_STYLES: Record<LevelKey, { label: string; color: string; dash?: string }> = {
  support: { label: "Support", color: COLORS.bull, dash: "2 3" },
  resistance: { label: "Resistance", color: COLORS.bear, dash: "2 3" },
  entry: { label: "Entry", color: COLORS.action, dash: "5 3" },
  stop: { label: "Stop", color: COLORS.bear, dash: "5 3" },
  tp1: { label: "TP1", color: COLORS.bull, dash: "5 3" },
  tp2: { label: "TP2", color: COLORS.bull, dash: "5 3" },
};

const INDICATOR_STYLES: Array<{
  key: IndicatorKey;
  label: string;
  color: string;
  dash?: string;
}> = [
  { key: "sma_20", label: "SMA 20", color: COLORS.trendFast },
  { key: "sma_50", label: "SMA 50", color: COLORS.trendMid },
  { key: "sma_200", label: "SMA 200", color: COLORS.trendSlow },
  { key: "bb_upper", label: "BB upper", color: COLORS.graphite, dash: "4 3" },
  { key: "bb_lower", label: "BB lower", color: COLORS.graphite, dash: "4 3" },
];

const INDICATOR_PREF_KEY = "priceChart:hiddenIndicators";
const OSCILLATOR_PREF_KEY = "priceChart:showOscillators";
const LEVEL_PREF_KEY = "priceChart:hiddenLevels";
/** Stable first-render coordinate space; ResizeObserver swaps in the real width after hydration. */
const CHART_WIDTH = 1000;

export function PriceChart({
  data,
  currency = "USD",
  technicals,
  supportLevels = [],
  resistanceLevels = [],
  actionPlan,
}: {
  data: ChartData;
  currency?: string;
  technicals?: ChartLatestIndicators | null;
  supportLevels?: number[];
  resistanceLevels?: number[];
  actionPlan?: ActionPlan | null;
}) {
  const [range, setRange] = React.useState<RangeKey>("6M");
  const [hoverIndex, setHoverIndex] = React.useState<number | null>(null);
  const [width, setWidth] = React.useState(CHART_WIDTH);
  const [hiddenIndicators, setHiddenIndicators] = React.useState<Set<IndicatorKey>>(
    () => new Set(),
  );
  const [showOscillators, setShowOscillators] = React.useState(true);
  const [hiddenLevels, setHiddenLevels] = React.useState<Set<LevelKey>>(() => new Set());
  const containerRef = React.useRef<HTMLDivElement>(null);

  React.useEffect(() => {
    try {
      const savedIndicators = localStorage.getItem(INDICATOR_PREF_KEY);
      if (savedIndicators) {
        setHiddenIndicators(new Set(JSON.parse(savedIndicators) as IndicatorKey[]));
      }
      const savedOscillators = localStorage.getItem(OSCILLATOR_PREF_KEY);
      if (savedOscillators != null) {
        setShowOscillators(savedOscillators === "true");
      }
      const savedLevels = localStorage.getItem(LEVEL_PREF_KEY);
      if (savedLevels) {
        setHiddenLevels(new Set(JSON.parse(savedLevels) as LevelKey[]));
      }
    } catch {
      // localStorage unavailable (e.g. private mode) — fall back to defaults.
    }
  }, []);

  React.useEffect(() => {
    const element = containerRef.current;
    if (!element) return;

    const update = () => setWidth(Math.max(1, Math.floor(element.getBoundingClientRect().width)));
    update();
    const observer = new ResizeObserver(update);
    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  function toggleLevel(key: LevelKey) {
    setHiddenLevels((previous) => {
      const next = new Set(previous);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      try {
        localStorage.setItem(LEVEL_PREF_KEY, JSON.stringify([...next]));
      } catch {
        // ignore persistence failures
      }
      return next;
    });
  }

  function toggleIndicator(key: IndicatorKey) {
    setHiddenIndicators((previous) => {
      const next = new Set(previous);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      try {
        localStorage.setItem(INDICATOR_PREF_KEY, JSON.stringify([...next]));
      } catch {
        // ignore persistence failures
      }
      return next;
    });
  }

  function toggleOscillators() {
    setShowOscillators((previous) => {
      const next = !previous;
      try {
        localStorage.setItem(OSCILLATOR_PREF_KEY, String(next));
      } catch {
        // ignore persistence failures
      }
      return next;
    });
  }

  const visibleIndicators = React.useMemo(
    () => INDICATOR_STYLES.filter((item) => !hiddenIndicators.has(item.key)),
    [hiddenIndicators],
  );

  const points = data[range];

  const hasSeries = points.some((point) => point.indicators?.rsi_14 != null);
  const renderOscillators = hasSeries && showOscillators;
  const height = renderOscillators ? 458 : 310;
  const layout = {
    left: 56,
    right: 72,
    top: 20,
    priceHeight: 190,
    volumeTop: 232,
    volumeHeight: 42,
    rsiTop: 307,
    rsiHeight: 48,
    macdTop: 378,
    macdHeight: 48,
  };
  const plotWidth = Math.max(1, width - layout.left - layout.right);

  const allReferenceLevels = React.useMemo(
    () => buildReferenceLevels(supportLevels, resistanceLevels, actionPlan),
    [actionPlan, resistanceLevels, supportLevels],
  );
  const visibleReferenceLevels = React.useMemo(
    () => allReferenceLevels.filter((level) => !hiddenLevels.has(level.key)),
    [allReferenceLevels, hiddenLevels],
  );

  const priceDomain = React.useMemo(() => {
    const values = [
      ...points.flatMap((point) => [point.high, point.low]),
      ...points.flatMap((point) => indicatorValues(point, visibleIndicators.map((item) => item.key))),
      ...visibleReferenceLevels.map((level) => level.value),
      ...(hasSeries
        ? []
        : latestIndicatorLevels(technicals, hiddenIndicators).map((level) => level.value)),
    ].filter(isFiniteNumber);
    return paddedDomain(values, 1);
  }, [hasSeries, hiddenIndicators, points, technicals, visibleIndicators, visibleReferenceLevels]);

  const volumeMax = React.useMemo(() => {
    const values = points.flatMap((point) => [point.volume, point.indicators?.volume_sma_20]);
    return Math.max(...values.filter(isFiniteNumber), 1);
  }, [points]);

  const macdDomain = React.useMemo(() => {
    const values = points.flatMap((point) =>
      indicatorValues(point, ["macd_line", "macd_signal", "macd_histogram"]),
    );
    return paddedDomain([...values, 0], 0.05);
  }, [points]);

  const xFor = (index: number) =>
    layout.left + (points.length <= 1 ? plotWidth / 2 : (index / (points.length - 1)) * plotWidth);
  const yPrice = (value: number) =>
    scale(value, priceDomain[0], priceDomain[1], layout.top + layout.priceHeight, layout.top);
  const yVolume = (value: number) =>
    scale(value, 0, volumeMax, layout.volumeTop + layout.volumeHeight, layout.volumeTop);
  const yRsi = (value: number) => scale(value, 0, 100, layout.rsiTop + layout.rsiHeight, layout.rsiTop);
  const yMacd = (value: number) =>
    scale(value, macdDomain[0], macdDomain[1], layout.macdTop + layout.macdHeight, layout.macdTop);

  const hovered = hoverIndex == null ? null : points[hoverIndex] ?? null;
  const change = points.length >= 2 ? points.at(-1)!.close - points[0].close : 0;
  const changePct = points[0]?.close ? (change / points[0].close) * 100 : 0;
  const up = change >= 0;
  const referenceLevels = visibleReferenceLevels.filter(
    (level) => level.value >= priceDomain[0] && level.value <= priceDomain[1],
  );

  function handlePointerMove(event: React.PointerEvent<SVGSVGElement>) {
    if (!points.length) return;
    const rect = event.currentTarget.getBoundingClientRect();
    const viewX = ((event.clientX - rect.left) / rect.width) * width;
    const raw = ((viewX - layout.left) / plotWidth) * Math.max(points.length - 1, 1);
    const next = Math.max(0, Math.min(points.length - 1, Math.round(raw)));
    setHoverIndex(next);
  }

  if (!points.length) {
    return <p className="text-sm text-graphite">No price history available.</p>;
  }

  return (
    <div ref={containerRef}>
      <div className="mb-4 flex flex-wrap items-end justify-between gap-4">
        <div>
          <div className="eyebrow">{range} range · OHLCV</div>
          <div className="mt-1 flex items-baseline gap-2.5">
            <span className="num text-2xl font-semibold tracking-tight text-ink md:text-3xl">
              {fmtCurrency(points.at(-1)?.close, currency)}
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
              {up ? "+" : ""}{fmtCurrency(change, currency)} · {fmtSignedPercent(changePct)}
            </span>
          </div>
        </div>
        <div className="inline-flex items-stretch overflow-hidden rounded-lg border bg-secondary p-0.5">
          {CHART_RANGES.map((item) => (
            <button
              key={item.key}
              type="button"
              onClick={() => {
                setRange(item.key);
                setHoverIndex(null);
              }}
              aria-pressed={range === item.key}
              className={cn(
                "num rounded px-2.5 py-1 text-micro font-medium transition-colors",
                range === item.key
                  ? "bg-action text-action-foreground"
                  : "text-graphite hover:text-action",
              )}
            >
              {item.key}
            </button>
          ))}
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-micro text-graphite">
        {INDICATOR_STYLES.map((item) => {
          const active = !hiddenIndicators.has(item.key);
          return (
            <button
              key={item.key}
              type="button"
              onClick={() => toggleIndicator(item.key)}
              aria-pressed={active}
              title={active ? `Hide ${item.label}` : `Show ${item.label}`}
              className={cn(
                "inline-flex items-center gap-1.5 rounded px-1 py-0.5 transition-opacity hover:bg-secondary",
                !active && "opacity-40",
              )}
            >
              <span
                className="inline-block h-px w-3"
                style={
                  item.dash
                    ? { borderTop: `1px dashed ${item.color}` }
                    : { backgroundColor: item.color }
                }
                aria-hidden
              />
              {item.label}
            </button>
          );
        })}
        {hasSeries && (
          <button
            type="button"
            onClick={toggleOscillators}
            aria-pressed={showOscillators}
            title={showOscillators ? "Hide RSI/MACD panels" : "Show RSI/MACD panels"}
            className={cn(
              "inline-flex items-center gap-1.5 rounded px-1 py-0.5 transition-opacity hover:bg-secondary",
              !showOscillators && "opacity-40",
            )}
          >
            RSI/MACD
          </button>
        )}
        <span className="text-action">dashed = bands</span>
        {!hasSeries && <span className="text-halt">historical indicators unavailable</span>}
      </div>

      {allReferenceLevels.length > 0 && (
        <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-micro text-graphite">
          {(Object.keys(LEVEL_STYLES) as LevelKey[])
            .filter((key) => allReferenceLevels.some((level) => level.key === key))
            .map((key) => {
              const style = LEVEL_STYLES[key];
              const active = !hiddenLevels.has(key);
              return (
                <button
                  key={key}
                  type="button"
                  onClick={() => toggleLevel(key)}
                  aria-pressed={active}
                  title={active ? `Hide ${style.label}` : `Show ${style.label}`}
                  className={cn(
                    "inline-flex items-center gap-1.5 rounded px-1 py-0.5 transition-opacity hover:bg-secondary",
                    !active && "opacity-40",
                  )}
                >
                  <span
                    className="inline-block h-px w-3"
                    style={
                      style.dash
                        ? { borderTop: `1px dashed ${style.color}` }
                        : { backgroundColor: style.color }
                    }
                    aria-hidden
                  />
                  {style.label}
                </button>
              );
            })}
        </div>
      )}

      <div className="relative mt-2 h-auto min-h-[220px] w-full">
        <svg
          width="100%"
          height={height}
          viewBox={`0 0 ${width} ${height}`}
          role="img"
          aria-label={describeChart(points, range, hasSeries)}
          onPointerMove={handlePointerMove}
          onPointerLeave={() => setHoverIndex(null)}
          className="block w-full overflow-visible"
        >
            <title>{range} price, volume, and technical indicators</title>
            <desc>{describeChart(points, range, hasSeries)}</desc>

            <rect
              x={layout.left}
              y={layout.top}
              width={plotWidth}
              height={layout.priceHeight}
              fill="transparent"
              stroke={COLORS.rule}
            />
            <rect
              x={layout.left}
              y={layout.volumeTop}
              width={plotWidth}
              height={layout.volumeHeight}
              fill="transparent"
              stroke={COLORS.rule}
            />

            {[0.25, 0.5, 0.75].map((fraction) => {
              const y = layout.top + layout.priceHeight * fraction;
              return (
                <line
                  key={fraction}
                  x1={layout.left}
                  x2={layout.left + plotWidth}
                  y1={y}
                  y2={y}
                  stroke={COLORS.rule}
                  strokeDasharray="2 4"
                />
              );
            })}

            <text x={layout.left - 8} y={layout.top - 6} textAnchor="end" className="num chart-label">
              Price
            </text>
            <text x={layout.left - 8} y={layout.volumeTop - 6} textAnchor="end" className="num chart-label">
              Volume
            </text>

            {hasSeries &&
              visibleIndicators.map((item) => (
                <path
                  key={item.key}
                  d={indicatorPath(points, item.key, xFor, yPrice)}
                  fill="none"
                  stroke={item.color}
                  strokeWidth={item.key === "sma_200" ? 1.5 : 1}
                  strokeDasharray={item.dash}
                  opacity={item.key.includes("bb_") ? 0.7 : 0.9}
                />
              ))}

            {!hasSeries &&
              latestIndicatorLevels(technicals, hiddenIndicators).map((level) => (
                <line
                  key={level.label}
                  x1={layout.left}
                  x2={layout.left + plotWidth}
                  y1={yPrice(level.value)}
                  y2={yPrice(level.value)}
                  stroke={level.color}
                  strokeDasharray={level.dash ?? "4 3"}
                  opacity={0.7}
                />
              ))}

            {referenceLevels.map((level, index) => (
              <g key={`${level.label}-${level.value}-${index}`}>
                <line
                  x1={layout.left}
                  x2={layout.left + plotWidth}
                  y1={yPrice(level.value)}
                  y2={yPrice(level.value)}
                  stroke={level.color}
                  strokeDasharray={level.dash ?? "2 3"}
                  opacity={0.65}
                />
                {level.label !== "Support" && level.label !== "Resistance" && (
                  <text
                    x={layout.left + plotWidth + 5}
                    y={yPrice(level.value) + 3}
                    className="num chart-label"
                    style={{ fill: level.color }}
                  >
                    {level.label} {fmtNumber(level.value)}
                  </text>
                )}
              </g>
            ))}

            {points.map((point, index) => {
              const x = xFor(index);
              const open = yPrice(point.open);
              const close = yPrice(point.close);
              const high = yPrice(point.high);
              const low = yPrice(point.low);
              const rising = point.close >= point.open;
              const candleColor = rising ? COLORS.bull : COLORS.bear;
              const bodyTop = Math.min(open, close);
              const bodyHeight = Math.max(1, Math.abs(open - close));
              const candleWidth = Math.max(1, Math.min(9, (plotWidth / points.length) * 0.62));
              return (
                <g key={point.date}>
                  <line x1={x} x2={x} y1={high} y2={low} stroke={candleColor} strokeWidth={1} />
                  <rect
                    x={x - candleWidth / 2}
                    y={bodyTop}
                    width={candleWidth}
                    height={bodyHeight}
                    fill={candleColor}
                    opacity={0.9}
                  />
                  <rect
                    x={x - candleWidth / 2}
                    y={yVolume(point.volume)}
                    width={candleWidth}
                    height={Math.max(1, layout.volumeTop + layout.volumeHeight - yVolume(point.volume))}
                    fill={candleColor}
                    opacity={0.55}
                  />
                </g>
              );
            })}

            <text x={layout.left - 8} y={layout.volumeTop + layout.volumeHeight} textAnchor="end" className="num chart-label">
              0
            </text>
            <text x={layout.left + plotWidth} y={layout.volumeTop - 6} textAnchor="end" className="num chart-label">
              {fmtCompactVolume(volumeMax)}
            </text>

            {renderOscillators && (
              <>
                <rect
                  x={layout.left}
                  y={layout.rsiTop}
                  width={plotWidth}
                  height={layout.rsiHeight}
                  fill="transparent"
                  stroke={COLORS.rule}
                />
                <rect
                  x={layout.left}
                  y={layout.macdTop}
                  width={plotWidth}
                  height={layout.macdHeight}
                  fill="transparent"
                  stroke={COLORS.rule}
                />
                <line
                  x1={layout.left}
                  x2={layout.left + plotWidth}
                  y1={yRsi(70)}
                  y2={yRsi(70)}
                  stroke={COLORS.bear}
                  strokeDasharray="3 3"
                  opacity={0.6}
                />
                <line
                  x1={layout.left}
                  x2={layout.left + plotWidth}
                  y1={yRsi(30)}
                  y2={yRsi(30)}
                  stroke={COLORS.bull}
                  strokeDasharray="3 3"
                  opacity={0.6}
                />
                <line
                  x1={layout.left}
                  x2={layout.left + plotWidth}
                  y1={yMacd(0)}
                  y2={yMacd(0)}
                  stroke={COLORS.rule}
                />
                <path
                  d={indicatorPath(points, "rsi_14", xFor, yRsi)}
                  fill="none"
                  stroke={COLORS.action}
                  strokeWidth={1.5}
                />
                <path
                  d={indicatorPath(points, "macd_line", xFor, yMacd)}
                  fill="none"
                  stroke={COLORS.bull}
                  strokeWidth={1.25}
                />
                <path
                  d={indicatorPath(points, "macd_signal", xFor, yMacd)}
                  fill="none"
                  stroke={COLORS.bear}
                  strokeWidth={1.25}
                />
                {points.map((point, index) => {
                  const value = point.indicators?.macd_histogram;
                  if (!isFiniteNumber(value)) return null;
                  const zero = yMacd(0);
                  const y = yMacd(value);
                  return (
                    <rect
                      key={`hist-${point.date}`}
                      x={xFor(index) - Math.max(1, (plotWidth / points.length) * 0.3)}
                      y={Math.min(y, zero)}
                      width={Math.max(1, (plotWidth / points.length) * 0.6)}
                      height={Math.max(1, Math.abs(zero - y))}
                      fill={value >= 0 ? COLORS.bull : COLORS.bear}
                      opacity={0.45}
                    />
                  );
                })}
                <text x={layout.left - 8} y={layout.rsiTop - 6} textAnchor="end" className="num chart-label">
                  RSI
                </text>
                <text x={layout.left - 8} y={layout.macdTop - 6} textAnchor="end" className="num chart-label">
                  MACD
                </text>
                <text x={layout.left + plotWidth + 5} y={yRsi(70) + 3} className="num chart-label" fill={COLORS.bear}>
                  70
                </text>
                <text x={layout.left + plotWidth + 5} y={yRsi(30) + 3} className="num chart-label" fill={COLORS.bull}>
                  30
                </text>
              </>
            )}

            {hovered && hoverIndex != null && (
              <line
                x1={xFor(hoverIndex)}
                x2={xFor(hoverIndex)}
                y1={layout.top}
                y2={renderOscillators ? layout.macdTop + layout.macdHeight : layout.volumeTop + layout.volumeHeight}
                stroke={COLORS.graphite}
                strokeDasharray="3 3"
              />
            )}

            {xTicks(points.length).map((index) => (
              <text
                key={`date-${index}`}
                x={xFor(index)}
                y={height - 8}
                textAnchor="middle"
                className="num chart-label"
              >
                {fmtDateShort(points[index].date)}
              </text>
            ))}
        </svg>

        {hovered && hoverIndex != null && (
          <div
            className="pointer-events-none absolute top-1 z-10 w-52 rounded-lg border bg-popover px-3 py-2 text-xs shadow-lg"
            style={{
              left: `${Math.min(Math.max(8, xFor(hoverIndex) - 104), Math.max(8, width - 216))}px`,
            }}
          >
            <div className="num text-micro font-medium text-graphite">{fmtDateShort(hovered.date)}</div>
            <div className="num mt-1 grid grid-cols-2 gap-x-3 gap-y-0.5 text-micro">
              <span className="text-graphite">O {fmtNumber(hovered.open)}</span>
              <span className="text-ink">C {fmtNumber(hovered.close)}</span>
              <span className="text-graphite">H {fmtNumber(hovered.high)}</span>
              <span className="text-graphite">L {fmtNumber(hovered.low)}</span>
              <span className="col-span-2 text-graphite">Vol {fmtCompactVolume(hovered.volume)}</span>
              {hovered.indicators?.rsi_14 != null && (
                <span className="col-span-2 text-action">
                  RSI {fmtNumber(hovered.indicators.rsi_14, 1)} · MACD {fmtNumber(hovered.indicators.macd_histogram, 2)}
                </span>
              )}
            </div>
          </div>
        )}
      </div>

      <p className="sr-only" aria-live="polite">
        {hovered
          ? `${fmtDateShort(hovered.date)} close ${fmtCurrency(hovered.close, currency)}.`
          : describeChart(points, range, hasSeries)}
      </p>
    </div>
  );
}

function indicatorValues(point: ChartPoint, keys: IndicatorKey[]): number[] {
  return keys
    .map((key) => point.indicators?.[key])
    .filter(isFiniteNumber);
}

function indicatorPath(
  points: ChartPoint[],
  key: IndicatorKey,
  xFor: (index: number) => number,
  yFor: (value: number) => number,
) {
  let path = "";
  let open = false;
  points.forEach((point, index) => {
    const value = point.indicators?.[key];
    if (!isFiniteNumber(value)) {
      open = false;
      return;
    }
    path += `${open ? "L" : "M"}${xFor(index)},${yFor(value)} `;
    open = true;
  });
  return path.trim();
}

function latestIndicatorLevels(
  technicals: ChartLatestIndicators | null | undefined,
  hiddenIndicators: Set<IndicatorKey>,
): LevelLine[] {
  if (!technicals) return [];
  const values: Partial<Record<IndicatorKey, number | null>> = {
    sma_20: technicals.sma_20,
    sma_50: technicals.sma_50,
    sma_200: technicals.sma_200,
    bb_upper: technicals.bb_upper,
    bb_lower: technicals.bb_lower,
  };
  return INDICATOR_STYLES.filter((item) => !hiddenIndicators.has(item.key))
    .flatMap((item): LevelLine[] => {
      const value = values[item.key];
      if (!isFiniteNumber(value)) return [];
      return [{ label: item.label, value, color: item.color, dash: item.dash }];
    });
}

function buildReferenceLevels(
  supportLevels: number[],
  resistanceLevels: number[],
  actionPlan?: ActionPlan | null,
): ReferenceLevel[] {
  return [
    ...supportLevels.map((value) => ({ key: "support" as const, ...LEVEL_STYLES.support, value })),
    ...resistanceLevels.map((value) => ({ key: "resistance" as const, ...LEVEL_STYLES.resistance, value })),
    ...(actionPlan?.entry_limit != null
      ? [{ key: "entry" as const, ...LEVEL_STYLES.entry, value: actionPlan.entry_limit }]
      : []),
    ...(actionPlan?.stop_loss != null
      ? [{ key: "stop" as const, ...LEVEL_STYLES.stop, value: actionPlan.stop_loss }]
      : []),
    ...(actionPlan?.take_profit_1 != null
      ? [{ key: "tp1" as const, ...LEVEL_STYLES.tp1, value: actionPlan.take_profit_1 }]
      : []),
    ...(actionPlan?.take_profit_2 != null
      ? [{ key: "tp2" as const, ...LEVEL_STYLES.tp2, value: actionPlan.take_profit_2 }]
      : []),
  ];
}

function paddedDomain(values: number[], minimumPadding: number): [number, number] {
  if (!values.length) return [0, 1];
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min;
  const padding = Math.max(span * 0.04, minimumPadding);
  return [min - padding, max + padding];
}

function scale(value: number, min: number, max: number, outputMin: number, outputMax: number) {
  if (max === min) return (outputMin + outputMax) / 2;
  return outputMin + ((value - min) / (max - min)) * (outputMax - outputMin);
}

function xTicks(length: number): number[] {
  if (length <= 1) return [0];
  const count = length < 80 ? 4 : 5;
  return Array.from({ length: count }, (_, index) =>
    Math.round((index / (count - 1)) * (length - 1)),
  ).filter((value, index, values) => values.indexOf(value) === index);
}

function isFiniteNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

function fmtCompactVolume(value: number): string {
  if (value >= 1_000_000_000) return `${(value / 1_000_000_000).toFixed(1)}B`;
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`;
  if (value >= 1_000) return `${(value / 1_000).toFixed(1)}K`;
  return Math.round(value).toLocaleString("en-US");
}

function describeChart(points: ChartPoint[], range: RangeKey, hasSeries: boolean) {
  return `${range} price chart with ${points.length} OHLC bars and volume. ${
    hasSeries ? "Historical RSI and MACD panels are available." : "Only latest indicator levels are available for this snapshot."
  }`;
}
