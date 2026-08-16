"use client";

import { useRouter } from "next/navigation";
import Link from "next/link";
import { ArrowDown, ArrowUp } from "lucide-react";
import { StarButton } from "@/components/ticker-list/star-button";
import { SignalBadge } from "@/components/briefing/signal-badge";
import {
  COLUMNS,
  isStale,
  STALE_DAYS,
  type ColumnDef,
  type SortDir,
  type SortKey,
} from "@/lib/screener";
import { fmtAge, fmtNumber, fmtSignedPercent } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { TickerSummary } from "@/lib/types";

/**
 * Data coloured, chrome neutral — the Bloomberg/TradingView pattern.
 *
 * Column heads, rules and row borders stay ink/graphite so the table reads as
 * neutral scaffolding; hue belongs to the cells that carry a reading. Direction
 * takes `bull`/`bear`, caveats (stale briefing, extreme RSI, desks that
 * disagree) take `halt`, and 52w stays graphite because it is context, not a
 * signal — colouring all twenty-six rows there is what made the first pass
 * unscannable.
 *
 * Colour is never the only carrier: weight (ink = worth reading), the direction
 * glyph, and a marker glyph backed by real sr-only text all still ride along.
 * Never a `title` alone.
 */

const HIDE_CLASS: Record<NonNullable<ColumnDef["hideBelow"]>, string> = {
  sm: "hidden sm:table-cell",
  md: "hidden md:table-cell",
  lg: "hidden lg:table-cell",
  xl: "hidden xl:table-cell",
};

/** Below this the four analyst desks disagree enough to distrust the levels. */
const LOW_CONVERGENCE = 0.5;
/** Conviction inside ±this band is a lean, not a call. */
const CONVICTION_LEAN = 0.15;
const RSI_OVERBOUGHT = 70;
const RSI_OVERSOLD = 30;

/**
 * The caveat mark. Small, shapely, and always paired with an sr-only reason.
 * It inherits its cell's colour so the mark and the number read as one token.
 */
function Marker({ reason }: { reason: string }) {
  return (
    <>
      <sup aria-hidden className="ml-0.5">
        °
      </sup>
      <span className="sr-only"> — {reason}</span>
    </>
  );
}

export function TickerTable({
  rows,
  sortKey,
  sortDir,
  onSort,
}: {
  rows: TickerSummary[];
  sortKey: SortKey;
  sortDir: SortDir;
  onSort: (key: SortKey) => void;
}) {
  const router = useRouter();

  return (
    <div className="overflow-x-auto rounded-lg border">
      <table className="w-full border-collapse text-sm">
        <caption className="sr-only">
          Watchlist screener. Sort with a column header; open a briefing with the
          symbol link in its row.
        </caption>
        <thead>
          <tr className="border-b bg-muted/40">
            {COLUMNS.map((c) => {
              const active = c.key === sortKey;
              return (
                <th
                  key={c.key}
                  scope="col"
                  aria-sort={
                    active
                      ? sortDir === "asc"
                        ? "ascending"
                        : "descending"
                      : "none"
                  }
                  className={cn(
                    "whitespace-nowrap p-0",
                    c.numeric ? "text-right" : "text-left",
                    c.key === "symbol" &&
                      "sticky left-0 z-10 bg-muted/40 backdrop-blur-sm",
                    c.hideBelow && HIDE_CLASS[c.hideBelow],
                  )}
                >
                  <button
                    type="button"
                    onClick={() => onSort(c.key)}
                    title={c.title}
                    className={cn(
                      "eyebrow inline-flex w-full items-center gap-1 px-2 py-2 transition-colors hover:text-ink",
                      c.numeric ? "justify-end" : "justify-start",
                      active && "text-ink",
                    )}
                  >
                    {c.label}
                    {active &&
                      (sortDir === "asc" ? (
                        <ArrowUp className="size-3" />
                      ) : (
                        <ArrowDown className="size-3" />
                      ))}
                  </button>
                </th>
              );
            })}
          </tr>
        </thead>
        <tbody>
          {rows.map((t) => {
            const lowConvergence =
              t.convergence != null && t.convergence < LOW_CONVERGENCE;
            const overbought = t.rsi14 != null && t.rsi14 >= RSI_OVERBOUGHT;
            const oversold = t.rsi14 != null && t.rsi14 <= RSI_OVERSOLD;
            const stale = isStale(t);
            const atEntry = t.toEntryPct != null && t.toEntryPct >= 0;
            const strongConviction =
              t.conviction != null && Math.abs(t.conviction) > CONVICTION_LEAN;

            return (
              <tr
                key={t.symbol}
                // Mouse-only shortcut, layered on top of the symbol link that
                // already does the job for keyboard and assistive tech. A <tr>
                // is not focusable, so this adds convenience, never the only way in.
                onClick={() => router.push(`/${t.symbol}`)}
                className="group cursor-pointer border-b transition-colors last:border-0 hover:bg-muted/50 focus-within:bg-muted/50"
              >
                <Td col="symbol" className="sticky left-0 z-10 bg-background">
                  <div className="flex items-center gap-1.5">
                    <StarButton symbol={t.symbol} />
                    <Link
                      href={`/${t.symbol}`}
                      onClick={(e) => e.stopPropagation()}
                      className="num font-semibold text-ink underline-offset-2 hover:underline group-hover:underline"
                    >
                      {t.symbol}
                    </Link>
                    <span className="rounded bg-muted px-1 py-px text-mini font-medium text-graphite">
                      {t.market}
                    </span>
                  </div>
                </Td>

                <Td col="name" className="max-w-[150px] truncate text-graphite">
                  {t.name}
                </Td>

                <Td col="price" className="num text-right tabular-nums text-ink">
                  {fmtNumber(t.price)}
                </Td>

                <Td col="signal">
                  {t.signal ? (
                    <SignalBadge signal={t.signal} size="sm" />
                  ) : (
                    <span className="text-mini text-graphite">
                      Not briefed
                      <span className="sr-only">
                        {" "}
                        — price data only, the analysis pipeline has not run
                      </span>
                    </span>
                  )}
                </Td>

                <Td
                  col="conviction"
                  className={cn(
                    "num text-right tabular-nums",
                    // A lean inside ±CONVICTION_LEAN is not a call, so it stays
                    // graphite; past the band it earns its direction colour.
                    !strongConviction
                      ? "text-graphite"
                      : (t.conviction ?? 0) > 0
                        ? "font-medium text-bull"
                        : "font-medium text-bear",
                  )}
                >
                  {t.conviction == null ? (
                    <>
                      —<span className="sr-only">No conviction score</span>
                    </>
                  ) : (
                    <>
                      {t.conviction >= 0 ? "+" : ""}
                      {t.conviction.toFixed(2)}
                      <span className="sr-only">
                        {" "}
                        conviction, where −1.00 is max bearish and +1.00 max bullish
                      </span>
                    </>
                  )}
                </Td>

                <Td
                  col="convergence"
                  className={cn(
                    "num text-right tabular-nums",
                    lowConvergence ? "font-medium text-halt" : "text-graphite",
                  )}
                >
                  {t.convergence == null ? (
                    "—"
                  ) : (
                    <>
                      {t.convergence.toFixed(2)}
                      {lowConvergence ? (
                        <Marker reason="the desks disagree; read the debate before acting" />
                      ) : (
                        <span className="sr-only"> agreement across the four desks</span>
                      )}
                    </>
                  )}
                </Td>

                <Td
                  col="toEntry"
                  className={cn(
                    "num text-right tabular-nums",
                    atEntry ? "font-medium text-bull" : "text-graphite",
                  )}
                  title={
                    t.entryLimit != null
                      ? `Entry limit ${fmtNumber(t.entryLimit)}${
                          t.stopLoss != null ? ` · stop ${fmtNumber(t.stopLoss)}` : ""
                        }${
                          t.takeProfit1 != null
                            ? ` · TP1 ${fmtNumber(t.takeProfit1)}`
                            : ""
                        }`
                      : undefined
                  }
                >
                  {t.toEntryPct == null ? (
                    <>
                      —
                      <span className="sr-only">
                        No entry level — bearish signal or no briefing
                      </span>
                    </>
                  ) : (
                    <>
                      {/* The signed number already carries direction — a glyph
                          on every row only adds ink. Weight plus `bull` marks
                          the rows that have actually reached their entry. */}
                      <span className={atEntry ? "font-medium" : undefined}>
                        {fmtSignedPercent(t.toEntryPct, 1)}
                      </span>
                      <span className="sr-only">
                        {atEntry
                          ? " — price is already at or below the entry limit"
                          : " — price must still fall to reach the entry limit"}
                      </span>
                    </>
                  )}
                </Td>

                <Td col="riskReward" className="num text-right tabular-nums text-graphite">
                  {t.riskReward == null ? "—" : `${t.riskReward.toFixed(2)}:1`}
                </Td>

                <Td col="pe" className="num text-right tabular-nums text-graphite">
                  {t.peRatio == null ? "—" : fmtNumber(t.peRatio, 1)}
                </Td>

                <Td
                  col="rsi"
                  className={cn(
                    "num text-right tabular-nums",
                    // Overbought reads bearish, oversold bullish — the colour
                    // follows what the reading implies, not the number's size.
                    overbought
                      ? "font-medium text-bear"
                      : oversold
                        ? "font-medium text-bull"
                        : "text-graphite",
                  )}
                >
                  {t.rsi14 == null ? (
                    "—"
                  ) : (
                    <>
                      {fmtNumber(t.rsi14, 1)}
                      {overbought && <Marker reason="overbought, RSI-14 at or above 70" />}
                      {oversold && <Marker reason="oversold, RSI-14 at or below 30" />}
                    </>
                  )}
                </Td>

                {/* Context, not a signal — every row has a value here, so
                    colouring the column would just tint the whole table. */}
                <Td col="from52wHigh" className="num text-right tabular-nums text-graphite">
                  {t.pctFrom52wHigh == null ? (
                    "—"
                  ) : (
                    <>
                      {fmtSignedPercent(t.pctFrom52wHigh * 100, 1)}
                      <span className="sr-only"> from the 52-week high</span>
                    </>
                  )}
                </Td>

                <Td
                  col="age"
                  className={cn(
                    "num text-right tabular-nums",
                    stale ? "font-medium text-halt" : "text-graphite",
                  )}
                  title={
                    t.briefingDate
                      ? `Briefing ${t.briefingDate}${
                          t.asOfDate ? ` · price data ${t.asOfDate}` : ""
                        }`
                      : undefined
                  }
                >
                  {t.briefingAgeDays == null ? (
                    <>
                      —<span className="sr-only">Never briefed</span>
                    </>
                  ) : (
                    <>
                      {fmtAge(t.briefingAgeDays)}
                      {stale ? (
                        <Marker
                          reason={`briefing is older than ${STALE_DAYS} days; the tape has moved on`}
                        />
                      ) : (
                        <span className="sr-only"> since this briefing was written</span>
                      )}
                    </>
                  )}
                </Td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

/** Cell that inherits its column's responsive-hide rule, so header and body stay aligned. */
function Td({
  col,
  className,
  title,
  children,
}: {
  col: SortKey;
  className?: string;
  title?: string;
  children: React.ReactNode;
}) {
  const def = COLUMNS.find((c) => c.key === col);
  return (
    <td
      title={title}
      className={cn(
        "whitespace-nowrap px-2 py-2",
        def?.hideBelow && HIDE_CLASS[def.hideBelow],
        className,
      )}
    >
      {children}
    </td>
  );
}
