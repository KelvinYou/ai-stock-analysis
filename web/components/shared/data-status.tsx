import Link from "next/link";
import { AlertTriangle } from "lucide-react";
import { CopyCommand } from "@/components/shared/copy-command";
import { fmtDateShort } from "@/lib/format";
import { isStale, STALE_DAYS } from "@/lib/screener";
import { cn } from "@/lib/utils";
import type { TickerSummary, WatchlistEntry } from "@/lib/types";

/**
 * Freshness and coverage of the whole desk, stated up front. Without this the
 * dashboard silently implies "you are looking at everything, as of now" — which
 * is wrong on both counts whenever the pipeline has not been run.
 */
export function DataStatus({
  tickers,
  watchlist,
}: {
  tickers: TickerSummary[];
  watchlist: WatchlistEntry[];
}) {
  const max = (values: (string | null)[]) =>
    values.filter((v): v is string => !!v).sort().at(-1) ?? null;

  const priceAsOf = max(tickers.map((t) => t.asOfDate));
  const briefedTickers = tickers.filter((t) => t.signal != null);
  const briefingAsOf = max(briefedTickers.map((t) => t.briefingDate));
  const staleCount = tickers.filter(isStale).length;

  const haveData = new Set(tickers.map((t) => t.symbol));
  const briefed = new Set(briefedTickers.map((t) => t.symbol));
  const notFetched = watchlist.filter((w) => !haveData.has(w.symbol));
  const unbriefedTracked = watchlist.filter(
    (w) => w.group === "tracked" && haveData.has(w.symbol) && !briefed.has(w.symbol),
  );

  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Stat
          label="Price data"
          value={priceAsOf ? fmtDateShort(priceAsOf) : "—"}
          hint={priceAsOf ?? "no price history"}
        />
        <Stat
          label="Newest briefing"
          value={briefingAsOf ? fmtDateShort(briefingAsOf) : "—"}
          hint={briefingAsOf ?? "no briefings yet"}
        />
        <Stat
          label="Briefed"
          value={`${briefedTickers.length}/${tickers.length}`}
          hint={`${tickers.length - briefedTickers.length} ticker(s) have Layer-1 data only`}
          tone={briefedTickers.length < tickers.length ? "warn" : undefined}
        />
        <Stat
          label={`Stale >${STALE_DAYS}d`}
          value={String(staleCount)}
          hint="Briefings the tape may have outrun"
          tone={staleCount > 0 ? "warn" : undefined}
        />
      </div>

      {unbriefedTracked.length > 0 && (
        <Gap
          title={`${unbriefedTracked.length} tracked ticker${
            unbriefedTracked.length > 1 ? "s" : ""
          } never briefed`}
          entries={unbriefedTracked}
        />
      )}

      {notFetched.length > 0 && (
        <Gap
          title={`${notFetched.length} watchlist ticker${
            notFetched.length > 1 ? "s" : ""
          } have no data at all`}
          entries={notFetched}
          fetchOnly
        />
      )}
    </div>
  );
}

function Stat({
  label,
  value,
  hint,
  tone,
}: {
  label: string;
  value: string;
  hint?: string;
  tone?: "warn";
}) {
  return (
    <div className="rounded-lg border bg-card p-3" title={hint}>
      <div className="text-[11px] font-medium text-muted-foreground">{label}</div>
      <div
        className={cn(
          "num mt-1 text-base font-semibold tracking-tight",
          tone === "warn" ? "text-amber-600" : "text-foreground",
        )}
      >
        {value}
      </div>
    </div>
  );
}

function Gap({
  title,
  entries,
  fetchOnly,
}: {
  title: string;
  entries: WatchlistEntry[];
  fetchOnly?: boolean;
}) {
  const cmd = fetchOnly
    ? `stock-fetch ${entries.map((e) => (e.market === "MY" ? `MY:${e.symbol}` : e.symbol)).join(" ")}`
    : entries
        .map((e) => `stock-analysis ${e.symbol} --market ${e.market}`)
        .join(" && ");

  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-2 rounded-lg border border-amber-500/30 bg-amber-500/5 px-3 py-2.5 text-xs">
      <span className="inline-flex items-center gap-1.5 font-medium text-amber-700 dark:text-amber-500">
        <AlertTriangle className="size-3.5" />
        {title}
      </span>
      <span className="flex flex-wrap gap-1">
        {entries.map((e) =>
          // A ticker with no data has no page to open — don't link into a 404.
          fetchOnly ? (
            <span
              key={e.symbol}
              className="num rounded border bg-background px-1.5 py-0.5 text-[11px] text-muted-foreground"
            >
              {e.symbol}
            </span>
          ) : (
            <Link
              key={e.symbol}
              href={`/${e.symbol}`}
              className="num rounded border bg-background px-1.5 py-0.5 text-[11px] text-foreground transition-colors hover:bg-muted"
            >
              {e.symbol}
            </Link>
          ),
        )}
      </span>
      <CopyCommand command={cmd} className="ml-auto" />
    </div>
  );
}
