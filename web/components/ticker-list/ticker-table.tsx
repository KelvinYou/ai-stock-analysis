"use client";

import { useRouter } from "next/navigation";
import Link from "next/link";
import { ArrowDown, ArrowUp } from "lucide-react";
import { StarButton } from "@/components/ticker-list/star-button";
import { SignalBadge } from "@/components/briefing/signal-badge";
import {
  COLUMNS,
  isStale,
  type ColumnDef,
  type SortDir,
  type SortKey,
} from "@/lib/screener";
import {
  fmtAge,
  fmtNumber,
  fmtSignedPercent,
} from "@/lib/format";
import { cn } from "@/lib/utils";
import type { TickerSummary } from "@/lib/types";

const HIDE_CLASS: Record<NonNullable<ColumnDef["hideBelow"]>, string> = {
  sm: "hidden sm:table-cell",
  md: "hidden md:table-cell",
  lg: "hidden lg:table-cell",
  xl: "hidden xl:table-cell",
};

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
    <div className="overflow-x-auto rounded-xl border">
      <table className="w-full border-collapse text-sm">
        <caption className="sr-only">
          Watchlist screener — click a column header to sort, click a row to open the
          briefing
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
                    "whitespace-nowrap p-0 text-[11px] font-medium",
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
                      "inline-flex w-full items-center gap-1 px-2 py-2 transition-colors hover:text-foreground",
                      c.numeric ? "justify-end" : "justify-start",
                      active ? "text-foreground" : "text-muted-foreground",
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
          {rows.map((t) => (
            <tr
              key={t.symbol}
              onClick={() => router.push(`/${t.symbol}`)}
              className="cursor-pointer border-b last:border-0 transition-colors hover:bg-muted/50"
            >
              <Td col="symbol" className="sticky left-0 z-10 bg-background">
                <div className="flex items-center gap-1.5">
                  <StarButton symbol={t.symbol} />
                  <Link
                    href={`/${t.symbol}`}
                    onClick={(e) => e.stopPropagation()}
                    className="num font-semibold text-foreground underline-offset-2 hover:underline"
                  >
                    {t.symbol}
                  </Link>
                  <span className="rounded bg-muted px-1 py-px text-[9px] font-medium text-muted-foreground">
                    {t.market}
                  </span>
                </div>
              </Td>

              <Td col="name" className="max-w-[150px] truncate text-muted-foreground">
                {t.name}
              </Td>

              <Td col="price" className="num text-right tabular-nums">
                {fmtNumber(t.price)}
              </Td>

              <Td col="signal">
                {t.signal ? (
                  <SignalBadge signal={t.signal} size="sm" />
                ) : (
                  <span
                    className="text-[10px] text-muted-foreground/60"
                    title="Layer-1 data only — no AI briefing yet"
                  >
                    data only
                  </span>
                )}
              </Td>

              <Td
                col="conviction"
                className={cn(
                  "num text-right tabular-nums font-medium",
                  t.conviction == null
                    ? "text-muted-foreground"
                    : t.conviction > 0.15
                      ? "text-emerald-600"
                      : t.conviction < -0.15
                        ? "text-rose-600"
                        : "text-foreground",
                )}
              >
                {t.conviction == null
                  ? "—"
                  : `${t.conviction >= 0 ? "+" : ""}${t.conviction.toFixed(2)}`}
              </Td>

              <Td
                col="convergence"
                className={cn(
                  "num text-right tabular-nums",
                  t.convergence != null && t.convergence < 0.5
                    ? "text-amber-600"
                    : "text-muted-foreground",
                )}
                title={
                  t.convergence != null && t.convergence < 0.5
                    ? "Agents disagree — read the debate before acting"
                    : undefined
                }
              >
                {t.convergence == null ? "—" : t.convergence.toFixed(2)}
              </Td>

              <Td
                col="toEntry"
                className={cn(
                  "num text-right tabular-nums",
                  t.toEntryPct == null
                    ? "text-muted-foreground"
                    : t.toEntryPct >= 0
                      ? "font-semibold text-emerald-600"
                      : "text-muted-foreground",
                )}
                title={
                  t.entryLimit != null
                    ? `Entry limit ${fmtNumber(t.entryLimit)}${
                        t.stopLoss != null ? ` · stop ${fmtNumber(t.stopLoss)}` : ""
                      }${
                        t.takeProfit1 != null ? ` · TP1 ${fmtNumber(t.takeProfit1)}` : ""
                      }`
                    : "No entry level — bearish or no briefing"
                }
              >
                {fmtSignedPercent(t.toEntryPct, 1)}
              </Td>

              <Td col="riskReward" className="num text-right tabular-nums text-muted-foreground">
                {t.riskReward == null ? "—" : `${t.riskReward.toFixed(2)}:1`}
              </Td>

              <Td col="pe" className="num text-right tabular-nums text-muted-foreground">
                {t.peRatio == null ? "—" : fmtNumber(t.peRatio, 1)}
              </Td>

              <Td
                col="rsi"
                className={cn(
                  "num text-right tabular-nums",
                  t.rsi14 == null
                    ? "text-muted-foreground"
                    : t.rsi14 >= 70
                      ? "text-amber-600"
                      : t.rsi14 <= 30
                        ? "text-sky-600"
                        : "text-muted-foreground",
                )}
                title={
                  t.rsi14 == null
                    ? undefined
                    : t.rsi14 >= 70
                      ? "Overbought"
                      : t.rsi14 <= 30
                        ? "Oversold"
                        : undefined
                }
              >
                {t.rsi14 == null ? "—" : fmtNumber(t.rsi14, 1)}
              </Td>

              <Td col="from52wHigh" className="num text-right tabular-nums text-muted-foreground">
                {t.pctFrom52wHigh == null
                  ? "—"
                  : fmtSignedPercent(t.pctFrom52wHigh * 100, 1)}
              </Td>

              <Td
                col="age"
                className={cn(
                  "num text-right tabular-nums",
                  isStale(t) ? "text-amber-600" : "text-muted-foreground",
                )}
                title={
                  t.briefingDate
                    ? `Briefing ${t.briefingDate}${
                        t.asOfDate ? ` · price data ${t.asOfDate}` : ""
                      }`
                    : "Never briefed"
                }
              >
                {fmtAge(t.briefingAgeDays)}
              </Td>
            </tr>
          ))}
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
