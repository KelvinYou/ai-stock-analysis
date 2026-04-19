"use client";

import { useMemo, useState, useEffect, useCallback } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { X } from "lucide-react";
import { TickerCard } from "./ticker-card";
import { cn } from "@/lib/utils";
import { signalLabel } from "@/lib/format";
import type { Signal, TickerSummary } from "@/lib/types";

type AnalyzedFilter = "all" | "briefed" | "raw";
type SortKey = "conviction" | "signal" | "change" | "symbol";

const SIGNAL_ORDER: Signal[] = ["strong_buy", "buy", "neutral", "sell", "strong_sell"];

const SIGNAL_WEIGHT: Record<Signal, number> = {
  strong_buy: 2,
  buy: 1,
  neutral: 0,
  sell: -1,
  strong_sell: -2,
};

const SIGNAL_DOT: Record<Signal, string> = {
  strong_buy: "bg-emerald-500",
  buy: "bg-emerald-500/70",
  neutral: "bg-zinc-400",
  sell: "bg-rose-500/70",
  strong_sell: "bg-rose-500",
};

const INITIAL_VISIBLE = 60;
const PAGE_SIZE = 60;

function parseSignals(raw: string | null): Set<Signal> {
  if (!raw) return new Set();
  const valid = new Set(SIGNAL_ORDER as string[]);
  const parts = raw.split(",").filter((s) => valid.has(s)) as Signal[];
  return new Set(parts);
}

function parseSet(raw: string | null): Set<string> {
  if (!raw) return new Set();
  return new Set(raw.split(",").map(decodeURIComponent).filter(Boolean));
}

export function TickerBrowser({ tickers }: { tickers: TickerSummary[] }) {
  const router = useRouter();
  const params = useSearchParams();

  const [search, setSearch] = useState(() => params.get("q") ?? "");
  const [signals, setSignals] = useState<Set<Signal>>(() =>
    parseSignals(params.get("signal")),
  );
  const [markets, setMarkets] = useState<Set<string>>(() =>
    parseSet(params.get("market")),
  );
  const [sectors, setSectors] = useState<Set<string>>(() =>
    parseSet(params.get("sector")),
  );
  const [analyzed, setAnalyzed] = useState<AnalyzedFilter>(() => {
    const v = params.get("analyzed");
    return v === "briefed" || v === "raw" ? v : "all";
  });
  const [sortKey, setSortKey] = useState<SortKey>(() => {
    const v = params.get("sort");
    return v === "signal" || v === "change" || v === "symbol" ? v : "conviction";
  });
  const [visible, setVisible] = useState(INITIAL_VISIBLE);

  const syncUrl = useCallback(
    (
      s: string,
      sig: Set<Signal>,
      mkt: Set<string>,
      sec: Set<string>,
      anl: AnalyzedFilter,
      srt: SortKey,
    ) => {
      const p = new URLSearchParams();
      if (s) p.set("q", s);
      if (sig.size) p.set("signal", [...sig].join(","));
      if (mkt.size) p.set("market", [...mkt].map(encodeURIComponent).join(","));
      if (sec.size) p.set("sector", [...sec].map(encodeURIComponent).join(","));
      if (anl !== "all") p.set("analyzed", anl);
      if (srt !== "conviction") p.set("sort", srt);
      const qs = p.toString();
      router.replace(qs ? `?${qs}` : "?", { scroll: false });
    },
    [router],
  );

  useEffect(() => {
    syncUrl(search, signals, markets, sectors, analyzed, sortKey);
  }, [search, signals, markets, sectors, analyzed, sortKey, syncUrl]);

  const briefedCount = useMemo(
    () => tickers.filter((t) => t.signal != null).length,
    [tickers],
  );

  const allMarkets = useMemo(
    () =>
      Array.from(new Set(tickers.map((t) => t.market).filter(Boolean))).sort(),
    [tickers],
  );
  const allSectors = useMemo(
    () =>
      Array.from(
        new Set(tickers.map((t) => t.sector).filter((s): s is string => !!s)),
      ).sort(),
    [tickers],
  );

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    const out = tickers.filter((t) => {
      if (
        q &&
        !t.symbol.toLowerCase().includes(q) &&
        !(t.name ?? "").toLowerCase().includes(q)
      )
        return false;
      if (analyzed === "briefed" && t.signal == null) return false;
      if (analyzed === "raw" && t.signal != null) return false;
      if (signals.size > 0 && (t.signal == null || !signals.has(t.signal)))
        return false;
      if (markets.size > 0 && !markets.has(t.market)) return false;
      if (sectors.size > 0 && (t.sector == null || !sectors.has(t.sector)))
        return false;
      return true;
    });
    out.sort((a, b) => {
      switch (sortKey) {
        case "conviction": {
          const ac = a.conviction ?? Number.NEGATIVE_INFINITY;
          const bc = b.conviction ?? Number.NEGATIVE_INFINITY;
          if (bc !== ac) return bc - ac;
          return a.symbol.localeCompare(b.symbol);
        }
        case "signal": {
          const aw = a.signal ? SIGNAL_WEIGHT[a.signal] : Number.NEGATIVE_INFINITY;
          const bw = b.signal ? SIGNAL_WEIGHT[b.signal] : Number.NEGATIVE_INFINITY;
          if (bw !== aw) return bw - aw;
          return a.symbol.localeCompare(b.symbol);
        }
        case "change": {
          const ac = a.priceChangePct ?? Number.NEGATIVE_INFINITY;
          const bc = b.priceChangePct ?? Number.NEGATIVE_INFINITY;
          if (bc !== ac) return bc - ac;
          return a.symbol.localeCompare(b.symbol);
        }
        case "symbol":
        default:
          return a.symbol.localeCompare(b.symbol);
      }
    });
    return out;
  }, [tickers, search, signals, markets, sectors, analyzed, sortKey]);

  const hasActiveFilters =
    search !== "" ||
    signals.size > 0 ||
    markets.size > 0 ||
    sectors.size > 0 ||
    analyzed !== "all";

  function reset() {
    setSearch("");
    setSignals(new Set());
    setMarkets(new Set());
    setSectors(new Set());
    setAnalyzed("all");
    setVisible(INITIAL_VISIBLE);
  }

  function toggleSet<T>(
    current: Set<T>,
    value: T,
    setter: (next: Set<T>) => void,
  ) {
    const next = new Set(current);
    if (next.has(value)) next.delete(value);
    else next.add(value);
    setter(next);
    setVisible(INITIAL_VISIBLE);
  }

  const shown = filtered.slice(0, visible);

  return (
    <div className="space-y-5">
      <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div className="flex flex-1 flex-col gap-3 sm:flex-row sm:items-center">
          <div className="relative w-full sm:max-w-xs">
            <input
              type="search"
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
                setVisible(INITIAL_VISIBLE);
              }}
              placeholder="Search symbol or name"
              className="h-9 w-full rounded-md border bg-background px-3 text-sm outline-none transition-colors placeholder:text-muted-foreground focus:border-foreground/30"
              aria-label="Search tickers"
            />
            {search && (
              <button
                type="button"
                onClick={() => setSearch("")}
                className="absolute right-2 top-1/2 -translate-y-1/2 rounded p-0.5 text-muted-foreground hover:bg-muted hover:text-foreground"
                aria-label="Clear search"
              >
                <X className="size-3.5" />
              </button>
            )}
          </div>
          <PillGroup
            value={analyzed}
            onChange={(v) => {
              setAnalyzed(v);
              setVisible(INITIAL_VISIBLE);
            }}
            options={[
              { v: "all", label: `All · ${tickers.length}` },
              { v: "briefed", label: `AI briefed · ${briefedCount}` },
              { v: "raw", label: "Data only" },
            ]}
          />
        </div>
        <div className="flex items-center gap-2">
          <label
            htmlFor="sort-select"
            className="text-[11px] font-medium text-muted-foreground"
          >
            Sort
          </label>
          <select
            id="sort-select"
            value={sortKey}
            onChange={(e) => setSortKey(e.target.value as SortKey)}
            className="h-9 rounded-md border bg-background px-2 text-sm outline-none transition-colors focus:border-foreground/30"
          >
            <option value="conviction">Conviction ↓</option>
            <option value="signal">Signal strength ↓</option>
            <option value="change">% change ↓</option>
            <option value="symbol">Symbol A–Z</option>
          </select>
        </div>
      </div>

      <FilterRow label="Signal">
        {SIGNAL_ORDER.map((s) => (
          <Chip
            key={s}
            active={signals.has(s)}
            onClick={() => toggleSet(signals, s, setSignals)}
          >
            <span
              className={cn("size-1.5 shrink-0 rounded-full", SIGNAL_DOT[s])}
              aria-hidden
            />
            {signalLabel(s)}
          </Chip>
        ))}
      </FilterRow>

      {allMarkets.length > 1 && (
        <FilterRow label="Market">
          {allMarkets.map((m) => (
            <Chip
              key={m}
              active={markets.has(m)}
              onClick={() => toggleSet(markets, m, setMarkets)}
            >
              {m}
            </Chip>
          ))}
        </FilterRow>
      )}

      {allSectors.length > 0 && (
        <FilterRow label="Sector">
          {allSectors.map((s) => (
            <Chip
              key={s}
              active={sectors.has(s)}
              onClick={() => toggleSet(sectors, s, setSectors)}
            >
              {s}
            </Chip>
          ))}
        </FilterRow>
      )}

      <div className="flex items-center justify-between border-t pt-4">
        <span className="text-xs text-muted-foreground">
          Showing{" "}
          <span className="num text-foreground">{shown.length}</span> of{" "}
          <span className="num">{filtered.length}</span>
          {filtered.length !== tickers.length && (
            <span className="text-muted-foreground/70">
              {" "}
              (filtered from {tickers.length})
            </span>
          )}
        </span>
        {hasActiveFilters && (
          <button
            type="button"
            onClick={reset}
            className="text-xs text-muted-foreground underline-offset-4 transition-colors hover:text-foreground hover:underline"
          >
            Reset filters
          </button>
        )}
      </div>

      {filtered.length === 0 ? (
        <div className="rounded-lg border border-dashed p-10 text-center text-sm text-muted-foreground">
          No tickers match these filters.
        </div>
      ) : (
        <>
          <div
            aria-label="Ticker list"
            className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3"
          >
            {shown.map((t, i) => (
              <div
                key={t.symbol}
                className="fade-up"
                style={{ animationDelay: `${Math.min(i * 20, 200)}ms` }}
              >
                <TickerCard t={t} />
              </div>
            ))}
          </div>
          {visible < filtered.length && (
            <div className="flex justify-center pt-2">
              <button
                type="button"
                onClick={() => setVisible((v) => v + PAGE_SIZE)}
                className="h-9 rounded-md border bg-background px-4 text-sm font-medium text-foreground transition-colors hover:bg-muted"
              >
                Load {Math.min(PAGE_SIZE, filtered.length - visible)} more
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
}

function FilterRow({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      <span className="w-14 shrink-0 text-[11px] font-medium text-muted-foreground">
        {label}
      </span>
      <div className="flex flex-wrap gap-1.5">{children}</div>
    </div>
  );
}

function Chip({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      aria-pressed={active}
      onClick={onClick}
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px] font-medium transition-colors",
        active
          ? "border-foreground/20 bg-foreground text-background"
          : "border-border bg-background text-muted-foreground hover:border-foreground/20 hover:text-foreground",
      )}
    >
      {children}
    </button>
  );
}

function PillGroup<T extends string>({
  value,
  onChange,
  options,
}: {
  value: T;
  onChange: (v: T) => void;
  options: { v: T; label: string }[];
}) {
  return (
    <div
      role="radiogroup"
      className="inline-flex h-9 items-center rounded-md border bg-background p-0.5"
    >
      {options.map((o) => (
        <button
          key={o.v}
          type="button"
          role="radio"
          aria-checked={value === o.v}
          onClick={() => onChange(o.v)}
          className={cn(
            "h-full rounded px-2.5 text-[12px] font-medium transition-colors",
            value === o.v
              ? "bg-muted text-foreground"
              : "text-muted-foreground hover:text-foreground",
          )}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}
