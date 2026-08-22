import type { PricePoint, TechnicalSeriesPoint, Technicals } from "./types";

export const CHART_RANGES = [
  { key: "1M", days: 30 },
  { key: "3M", days: 90 },
  { key: "6M", days: 180 },
  { key: "1Y", days: 365 },
  { key: "ALL", days: Number.POSITIVE_INFINITY },
] as const;

export type ChartRangeKey = (typeof CHART_RANGES)[number]["key"];

/** The only historical indicators the chart can render or describe. */
export type ChartIndicatorPoint = Pick<
  TechnicalSeriesPoint,
  | "date"
  | "sma_20"
  | "sma_50"
  | "sma_200"
  | "rsi_14"
  | "macd_line"
  | "macd_signal"
  | "macd_histogram"
  | "bb_upper"
  | "bb_lower"
  | "volume_sma_20"
>;

export type ChartPoint = PricePoint & {
  indicators: ChartIndicatorPoint | null;
};

export type ChartData = Record<ChartRangeKey, ChartPoint[]>;

/** Latest levels are used only when a historical technical series is absent. */
export type ChartLatestIndicators = Pick<
  Technicals,
  "sma_20" | "sma_50" | "sma_200" | "bb_upper" | "bb_lower"
>;

const MAX_CHART_BARS = 220;

/**
 * Build the small, range-aware payload consumed by the client chart.
 *
 * The page may load a full historical bundle on the server, but the client
 * only needs the visible OHLC bars and the indicators it can draw.
 */
export function buildChartData(
  priceHistory: PricePoint[],
  series: TechnicalSeriesPoint[],
): ChartData {
  const seriesByDate = new Map(series.map((point) => [point.date, point]));

  return Object.fromEntries(
    CHART_RANGES.map(({ key, days }) => {
      const ranged = Number.isFinite(days) ? priceHistory.slice(-days) : priceHistory;
      const joined = ranged.map((bar) => ({
        ...bar,
        indicators: projectIndicators(seriesByDate.get(bar.date)),
      }));
      return [key, aggregateBars(joined, MAX_CHART_BARS)];
    }),
  ) as ChartData;
}

export function chartLatestIndicators(
  technicals: Technicals | null | undefined,
): ChartLatestIndicators | null {
  if (!technicals) return null;
  return {
    sma_20: technicals.sma_20,
    sma_50: technicals.sma_50,
    sma_200: technicals.sma_200,
    bb_upper: technicals.bb_upper,
    bb_lower: technicals.bb_lower,
  };
}

function projectIndicators(
  point: TechnicalSeriesPoint | undefined,
): ChartIndicatorPoint | null {
  if (!point) return null;
  return {
    date: point.date,
    sma_20: point.sma_20,
    sma_50: point.sma_50,
    sma_200: point.sma_200,
    rsi_14: point.rsi_14,
    macd_line: point.macd_line,
    macd_signal: point.macd_signal,
    macd_histogram: point.macd_histogram,
    bb_upper: point.bb_upper,
    bb_lower: point.bb_lower,
    volume_sma_20: point.volume_sma_20,
  };
}

function aggregateBars(points: ChartPoint[], maxBars: number): ChartPoint[] {
  if (points.length <= maxBars) return points;
  const size = Math.ceil(points.length / maxBars);
  const output: ChartPoint[] = [];

  for (let start = 0; start < points.length; start += size) {
    const chunk = points.slice(start, start + size);
    const first = chunk[0];
    const last = chunk.at(-1)!;
    output.push({
      ...last,
      open: first.open,
      high: Math.max(...chunk.map((point) => point.high)),
      low: Math.min(...chunk.map((point) => point.low)),
      volume: chunk.reduce((sum, point) => sum + point.volume, 0),
    });
  }

  return output;
}
