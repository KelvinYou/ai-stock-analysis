"use client";

import { useMemo, useState, useEffect, useCallback } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { LayoutGrid, Rows3, SlidersHorizontal, X } from "lucide-react";
import { TickerCard } from "./ticker-card";
import { TickerTable } from "./ticker-table";
import { cn } from "@/lib/utils";
import { signalLabel } from "@/lib/format";
import {
  COLUMNS,
  isActionable,
  isStale,
  sortRows,
  STALE_DAYS,
  type SortDir,
  type SortKey,
} from "@/lib/screener";
import type { Signal, TickerSummary } from "@/lib/types";

type AnalyzedFilter = "all" | "briefed" | "raw";
type GroupFilter = "all" | "holding" | "candidate";
type View = "table" | "cards";

const SIGNAL_ORDER: Signal[] = ["strong_buy", "buy", "neutral", "sell", "strong_sell"];

const SIGNAL_DOT: Record<Signal, string> = {
  strong_buy: "bg-emerald-500",
  buy: "bg-emerald-500/70",
  neutral: "bg-zinc-400",
  sell: "bg-rose-500/70",
  strong_sell: "bg-rose-500",
};

const VIEW_KEY = "desk.view.v1";
const INITIAL_VISIBLE = 60;
const PAGE_SIZE = 60;
const SORT_KEYS = new Set<string>(COLUMNS.map((c) => c.key));

function parseSignals(raw: string | null): Set<Signal> {
  if (!raw) return new Set();
  const valid = new Set(SIGNAL_ORDER as string[]);
  return new Set(raw.split(",").filter((s) => valid.has(s)) as Signal[]);
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
  const [themes, setThemes] = useState<Set<string>>(() => parseSet(params.get("theme")));
  const [analyzed, setAnalyzed] = useState<AnalyzedFilter>(() => {
    const v = params.get("analyzed");
    return v === "briefed" || v === "raw" ? v : "all";
  });
  const [group, setGroup] = useState<GroupFilter>(() => {
    const v = params.get("group");
    return v === "holding" || v === "candidate" ? v : "all";
  });
  const [actionableOnly, setActionableOnly] = useState(
    () => params.get("actionable") === "1",
  );
  const [staleOnly, setStaleOnly] = useState(() => params.get("stale") === "1");
  const [sortKey, setSortKey] = useState<SortKey>(() => {
    const v = params.get("sort");
    return v && SORT_KEYS.has(v) ? (v as SortKey) : "conviction";
  });
  const [sortDir, setSortDir] = useState<SortDir>(() =>
    params.get("dir") === "asc" ? "asc" : "desc",
  );
  const [view, setView] = useState<View>(() =>
    params.get("view") === "cards" ? "cards" : "table",
  );
  const [moreFilters, setMoreFilters] = useState(
    () =>
      parseSet(params.get("market")).size > 0 ||
      parseSet(params.get("sector")).size > 0 ||
      parseSet(params.get("theme")).size > 0,
  );
  const [visible, setVisible] = useState(INITIAL_VISIBLE);

  // Remember the view across sessions; an explicit ?view= in the URL wins.
  useEffect(() => {
    if (params.get("view")) return;
    const stored = localStorage.getItem(VIEW_KEY);
    if (stored === "cards" || stored === "table") setView(stored);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    localStorage.setItem(VIEW_KEY, view);
  }, [view]);

  const syncUrl = useCallback(() => {
    const p = new URLSearchParams();
    if (search) p.set("q", search);
    if (signals.size) p.set("signal", [...signals].join(","));
    if (markets.size) p.set("market", [...markets].map(encodeURIComponent).join(","));
    if (sectors.size) p.set("sector", [...sectors].map(encodeURIComponent).join(","));
    if (themes.size) p.set("theme", [...themes].map(encodeURIComponent).join(","));
    if (analyzed !== "all") p.set("analyzed", analyzed);
    if (group !== "all") p.set("group", group);
    if (actionableOnly) p.set("actionable", "1");
    if (staleOnly) p.set("stale", "1");
    if (sortKey !== "conviction") p.set("sort", sortKey);
    if (sortDir !== "desc") p.set("dir", sortDir);
    if (view !== "table") p.set("view", view);
    const qs = p.toString();
    router.replace(qs ? `?${qs}` : "?", { scroll: false });
  }, [
    router,
    search,
    signals,
    markets,
    sectors,
    themes,
    analyzed,
    group,
    actionableOnly,
    staleOnly,
    sortKey,
    sortDir,
    view,
  ]);

  useEffect(() => {
    syncUrl();
  }, [syncUrl]);

  const counts = useMemo(
    () => ({
      briefed: tickers.filter((t) => t.signal != null).length,
      actionable: tickers.filter(isActionable).length,
      stale: tickers.filter(isStale).length,
      holdings: tickers.filter((t) => t.group === "holding").length,
    }),
    [tickers],
  );

  const allMarkets = useMemo(
    () => Array.from(new Set(tickers.map((t) => t.market).filter(Boolean))).sort(),
    [tickers],
  );
  const allSectors = useMemo(
    () =>
      Array.from(
        new Set(tickers.map((t) => t.sector).filter((s): s is string => !!s)),
      ).sort(),
    [tickers],
  );
  const allThemes = useMemo(
    () =>
      Array.from(
        new Set(tickers.map((t) => t.theme).filter((s): s is string => !!s)),
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
      if (group !== "all" && t.group !== group) return false;
      if (actionableOnly && !isActionable(t)) return false;
      if (staleOnly && !isStale(t)) return false;
      if (signals.size > 0 && (t.signal == null || !signals.has(t.signal))) return false;
      if (markets.size > 0 && !markets.has(t.market)) return false;
      if (sectors.size > 0 && (t.sector == null || !sectors.has(t.sector))) return false;
      if (themes.size > 0 && (t.theme == null || !themes.has(t.theme))) return false;
      return true;
    });
    return sortRows(out, sortKey, sortDir);
  }, [
    tickers,
    search,
    signals,
    markets,
    sectors,
    themes,
    analyzed,
    group,
    actionableOnly,
    staleOnly,
    sortKey,
    sortDir,
  ]);

  const hasActiveFilters =
    search !== "" ||
    signals.size > 0 ||
    markets.size > 0 ||
    sectors.size > 0 ||
    themes.size > 0 ||
    analyzed !== "all" ||
    group !== "all" ||
    actionableOnly ||
    staleOnly;

  function reset() {
    setSearch("");
    setSignals(new Set());
    setMarkets(new Set());
    setSectors(new Set());
    setThemes(new Set());
    setAnalyzed("all");
    setGroup("all");
    setActionableOnly(false);
    setStaleOnly(false);
    setVisible(INITIAL_VISIBLE);
  }

  function toggleSet<T>(current: Set<T>, value: T, setter: (next: Set<T>) => void) {
    const next = new Set(current);
    if (next.has(value)) next.delete(value);
    else next.add(value);
    setter(next);
    setVisible(INITIAL_VISIBLE);
  }

  /** Same header click cycles direction; a new header starts at its natural direction. */
  function handleSort(key: SortKey) {
    if (key === sortKey) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
      return;
    }
    setSortKey(key);
    setSortDir(COLUMNS.find((c) => c.key === key)?.defaultDir ?? "desc");
  }

  const shown = filtered.slice(0, visible);

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div className="flex flex-1 flex-wrap items-center gap-2">
          <div className="relative w-full sm:max-w-[220px]">
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
            label="Analysis"
            value={analyzed}
            onChange={(v) => {
              setAnalyzed(v);
              setVisible(INITIAL_VISIBLE);
            }}
            options={[
              { v: "all", label: `All · ${tickers.length}` },
              { v: "briefed", label: `Briefed · ${counts.briefed}` },
              { v: "raw", label: "Data only" },
            ]}
          />
          <PillGroup
            label="Position"
            value={group}
            onChange={(v) => {
              setGroup(v);
              setVisible(INITIAL_VISIBLE);
            }}
            options={[
              { v: "all", label: "Any" },
              { v: "holding", label: `Held · ${counts.holdings}` },
              { v: "candidate", label: "Candidates" },
            ]}
          />
        </div>

        <div className="flex items-center gap-2">
          <label htmlFor="sort-select" className="sr-only">
            Sort by
          </label>
          <select
            id="sort-select"
            value={sortKey}
            onChange={(e) => handleSort(e.target.value as SortKey)}
            className="h-9 rounded-md border bg-background px-2 text-xs outline-none transition-colors focus:border-foreground/30"
          >
            {COLUMNS.map((c) => (
              <option key={c.key} value={c.key}>
                Sort: {c.label}
              </option>
            ))}
          </select>
          <button
            type="button"
            onClick={() => setSortDir((d) => (d === "asc" ? "desc" : "asc"))}
            className="h-9 rounded-md border bg-background px-2.5 text-xs text-muted-foreground transition-colors hover:text-foreground"
            aria-label={`Sort direction: ${sortDir === "asc" ? "ascending" : "descending"}`}
          >
            {sortDir === "asc" ? "↑" : "↓"}
          </button>
          <div
            role="radiogroup"
            aria-label="View"
            className="inline-flex h-9 items-center rounded-md border bg-background p-0.5"
          >
            {(
              [
                { v: "table" as View, Icon: Rows3, label: "Table" },
                { v: "cards" as View, Icon: LayoutGrid, label: "Cards" },
              ]
            ).map(({ v, Icon, label }) => (
              <button
                key={v}
                type="button"
                role="radio"
                aria-checked={view === v}
                aria-label={label}
                onClick={() => setView(v)}
                className={cn(
                  "grid h-full w-8 place-items-center rounded transition-colors",
                  view === v
                    ? "bg-muted text-foreground"
                    : "text-muted-foreground hover:text-foreground",
                )}
              >
                <Icon className="size-4" />
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-1.5">
        <Chip
          active={actionableOnly}
          disabled={counts.actionable === 0 && !actionableOnly}
          onClick={() => {
            setActionableOnly((v) => !v);
            setVisible(INITIAL_VISIBLE);
          }}
          title="Last close has reached the suggested entry limit"
        >
          <span className="size-1.5 shrink-0 rounded-full bg-emerald-500" aria-hidden />
          At entry · {counts.actionable}
        </Chip>
        <Chip
          active={staleOnly}
          disabled={counts.stale === 0 && !staleOnly}
          onClick={() => {
            setStaleOnly((v) => !v);
            setVisible(INITIAL_VISIBLE);
          }}
          title={`Briefing older than ${STALE_DAYS} days`}
        >
          <span className="size-1.5 shrink-0 rounded-full bg-amber-500" aria-hidden />
          Stale &gt;{STALE_DAYS}d · {counts.stale}
        </Chip>
        <span className="mx-1 h-4 w-px bg-border" aria-hidden />
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
        <button
          type="button"
          onClick={() => setMoreFilters((v) => !v)}
          aria-expanded={moreFilters}
          className={cn(
            "ml-1 inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px] font-medium transition-colors",
            moreFilters
              ? "border-foreground/20 text-foreground"
              : "border-border text-muted-foreground hover:text-foreground",
          )}
        >
          <SlidersHorizontal className="size-3" />
          More
        </button>
      </div>

      {moreFilters && (
        <div className="space-y-2.5 rounded-lg border bg-muted/20 p-3">
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
          {allThemes.length > 0 && (
            <FilterRow label="Theme">
              {allThemes.map((t) => (
                <Chip
                  key={t}
                  active={themes.has(t)}
                  onClick={() => toggleSet(themes, t, setThemes)}
                >
                  {t}
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
        </div>
      )}

      <div className="flex items-center justify-between border-t pt-3">
        <span className="text-xs text-muted-foreground">
          Showing <span className="num text-foreground">{shown.length}</span> of{" "}
          <span className="num">{filtered.length}</span>
          {filtered.length !== tickers.length && (
            <span className="text-muted-foreground/70"> (of {tickers.length})</span>
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
          {view === "table" ? (
            <TickerTable
              rows={shown}
              sortKey={sortKey}
              sortDir={sortDir}
              onSort={handleSort}
            />
          ) : (
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
          )}
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

function FilterRow({ label, children }: { label: string; children: React.ReactNode }) {
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
  title,
  disabled,
  children,
}: {
  active: boolean;
  onClick: () => void;
  title?: string;
  disabled?: boolean;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      aria-pressed={active}
      onClick={onClick}
      title={title}
      disabled={disabled}
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px] font-medium transition-colors",
        active
          ? "border-foreground/20 bg-foreground text-background"
          : "border-border bg-background text-muted-foreground hover:border-foreground/20 hover:text-foreground",
        disabled && "cursor-not-allowed opacity-40 hover:border-border hover:text-muted-foreground",
      )}
    >
      {children}
    </button>
  );
}

function PillGroup<T extends string>({
  label,
  value,
  onChange,
  options,
}: {
  label: string;
  value: T;
  onChange: (v: T) => void;
  options: { v: T; label: string }[];
}) {
  return (
    <div
      role="radiogroup"
      aria-label={label}
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
