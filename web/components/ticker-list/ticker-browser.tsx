"use client";

import { useMemo, useState, useEffect, useCallback } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { getMyList } from "@/lib/client-storage";
import { LayoutGrid, Rows3, SlidersHorizontal, X } from "lucide-react";
import { TickerCard } from "./ticker-card";
import { TickerTable } from "./ticker-table";
import { ConvictionMap } from "@/components/consensus/conviction-map";
import { cn } from "@/lib/utils";
import { signalGlyph, signalShortLabel } from "@/lib/signal-display";
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
type View = "table" | "cards";

const SIGNAL_ORDER: Signal[] = ["strong_buy", "buy", "neutral", "sell", "strong_sell"];

/**
 * The chip row is where the colour vocabulary gets taught: the glyph carries its
 * signal's hue, so by the time you reach the table you already know what a green
 * conviction number means. The chip container itself stays interactive-blue —
 * "you can click this" must never read as "this went up".
 */
const SIGNAL_TONE: Record<Signal, string> = {
  strong_buy: "text-bull",
  buy: "text-bull",
  neutral: "text-graphite",
  sell: "text-bear",
  strong_sell: "text-bear",
};

const VIEW_KEY = "desk.view.v1";
const INITIAL_VISIBLE = 60;
const PAGE_SIZE = 60;
/** Cards enter in a short cascade; the last card in view must not wait for it. */
const CARD_STAGGER_MS = 20;
const MAX_CARD_STAGGER_MS = 200;
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
  const [actionableOnly, setActionableOnly] = useState(
    () => params.get("actionable") === "1",
  );
  const [staleOnly, setStaleOnly] = useState(() => params.get("stale") === "1");
  const [starredOnly, setStarredOnly] = useState(() => params.get("starred") === "1");

  // The sidebar caps "My list" to keep the rail inside one viewport, so its
  // overflow link lands here — the filter has to actually exist for that.
  const [starred, setStarred] = useState<Set<string>>(new Set());
  useEffect(() => {
    const refresh = () => setStarred(new Set(getMyList()));
    refresh();
    window.addEventListener("mylist-change", refresh);
    return () => window.removeEventListener("mylist-change", refresh);
  }, []);
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
    if (actionableOnly) p.set("actionable", "1");
    if (staleOnly) p.set("stale", "1");
    if (starredOnly) p.set("starred", "1");
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
    actionableOnly,
    staleOnly,
    starredOnly,
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
      starred: tickers.filter((t) => starred.has(t.symbol)).length,
    }),
    [tickers, starred],
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
      if (actionableOnly && !isActionable(t)) return false;
      if (staleOnly && !isStale(t)) return false;
      if (starredOnly && !starred.has(t.symbol)) return false;
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
    actionableOnly,
    staleOnly,
    starredOnly,
    starred,
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
    actionableOnly ||
    staleOnly ||
    starredOnly;

  function reset() {
    setSearch("");
    setSignals(new Set());
    setMarkets(new Set());
    setSectors(new Set());
    setThemes(new Set());
    setAnalyzed("all");
    setActionableOnly(false);
    setStaleOnly(false);
    setStarredOnly(false);
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
            <label htmlFor="ticker-search" className="sr-only">
              Search tickers
            </label>
            <input
              id="ticker-search"
              type="search"
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
                setVisible(INITIAL_VISIBLE);
              }}
              placeholder="Search symbol or name"
              className="h-9 w-full rounded-md border bg-background px-3 text-sm transition-colors placeholder:text-graphite focus:border-action"
            />
            {search && (
              <button
                type="button"
                onClick={() => setSearch("")}
                className="absolute right-2 top-1/2 -translate-y-1/2 rounded p-0.5 text-graphite hover:bg-muted hover:text-ink"
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
              { v: "raw", label: "Not briefed" },
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
            className="h-9 rounded-md border bg-background px-2 text-xs transition-colors focus:border-action"
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
            className="h-9 rounded-md border bg-background px-2.5 text-xs text-graphite transition-colors hover:text-ink"
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
                  view === v ? "bg-muted text-ink" : "text-graphite hover:text-ink",
                )}
              >
                <Icon className="size-4" />
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-1.5">
        {counts.starred > 0 && (
          <Chip
            active={starredOnly}
            onClick={() => {
              setStarredOnly((v) => !v);
              setVisible(INITIAL_VISIBLE);
            }}
            title="Only the tickers you have starred"
          >
            <span aria-hidden className="text-halt">
              ★
            </span>
            My list · {counts.starred}
          </Chip>
        )}
        <Chip
          active={actionableOnly}
          disabled={counts.actionable === 0 && !actionableOnly}
          onClick={() => {
            setActionableOnly((v) => !v);
            setVisible(INITIAL_VISIBLE);
          }}
          title="Last close has reached the suggested entry limit"
        >
          <span aria-hidden className="text-bull">
            ▲
          </span>
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
          <span aria-hidden className="text-halt">
            °
          </span>
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
              aria-hidden
              className={cn("shrink-0", signals.has(s) && SIGNAL_TONE[s])}
            >
              {signalGlyph(s)}
            </span>
            {signalShortLabel(s)}
          </Chip>
        ))}
        <button
          type="button"
          onClick={() => setMoreFilters((v) => !v)}
          aria-expanded={moreFilters}
          className={cn(
            "ml-1 inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-micro font-medium transition-colors",
            moreFilters ? "border-ink text-ink" : "border-rule text-graphite hover:text-ink",
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

      <ConvictionMap tickers={filtered} />

      <div className="flex items-center justify-between border-t pt-3">
        <span className="text-xs text-graphite">
          Showing <span className="num text-ink">{shown.length}</span> of{" "}
          <span className="num text-ink">{filtered.length}</span> matching
          {filtered.length !== tickers.length && (
            <span>
              {" "}
              · <span className="num">{tickers.length}</span> tickers in total
            </span>
          )}
        </span>
        {hasActiveFilters && (
          <button
            type="button"
            onClick={reset}
            className="text-xs text-graphite underline-offset-4 transition-colors hover:text-ink hover:underline"
          >
            Reset filters
          </button>
        )}
      </div>

      {filtered.length === 0 ? (
        <div className="rounded-lg border border-dashed p-10 text-center">
          <p className="text-sm text-ink">No ticker matches these filters.</p>
          <p className="mt-1 text-xs text-graphite">
            Widen the filters or reset them to see all{" "}
            <span className="num">{tickers.length}</span> tickers.
          </p>
          {hasActiveFilters && (
            <button
              type="button"
              onClick={reset}
              className="mt-4 h-9 rounded-md border bg-background px-4 text-sm font-medium text-ink transition-colors hover:bg-muted"
            >
              Reset filters
            </button>
          )}
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
                  style={{
                    animationDelay: `${Math.min(i * CARD_STAGGER_MS, MAX_CARD_STAGGER_MS)}ms`,
                  }}
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
                className="h-9 rounded-md border bg-background px-4 text-sm font-medium text-ink transition-colors hover:bg-muted"
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
      <span className="eyebrow w-14 shrink-0">{label}</span>
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
        "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-micro font-medium transition-colors",
        // A chip is something you clicked, not something that went up — so the
        // active state is `action`, never a direction colour.
        active
          ? "border-action bg-action/10 text-action"
          : "border-rule bg-background text-graphite hover:border-ink hover:text-ink",
        disabled && "cursor-not-allowed opacity-40 hover:border-rule hover:text-graphite",
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
            "h-full rounded px-2.5 text-xs font-medium transition-colors",
            value === o.v ? "bg-muted text-ink" : "text-graphite hover:text-ink",
          )}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}
