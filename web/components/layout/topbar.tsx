"use client";

import { Fragment, useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { useRouter, usePathname } from "next/navigation";
import { ChevronRight, Menu, Search } from "lucide-react";
import { cn } from "@/lib/utils";
import type { Signal, TickerSummary } from "@/lib/types";

const SIGNAL_DOT: Record<Signal, string> = {
  strong_buy: "bg-emerald-500",
  buy: "bg-emerald-500/70",
  neutral: "bg-zinc-400",
  sell: "bg-rose-500/70",
  strong_sell: "bg-rose-500",
};

export function Topbar({
  onMenuClick,
  tickers,
}: {
  onMenuClick: () => void;
  tickers: TickerSummary[];
}) {
  const pathname = usePathname();
  const crumbs = buildCrumbs(pathname);
  const [searchOpen, setSearchOpen] = useState(false);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setSearchOpen((v) => !v);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  return (
    <header className="sticky top-0 z-30 flex h-16 shrink-0 items-center justify-between gap-4 border-b bg-background/80 px-5 backdrop-blur-md md:px-10">
      <div className="flex min-w-0 items-center gap-3">
        <button
          type="button"
          onClick={onMenuClick}
          className="-ml-1 inline-flex size-9 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring lg:hidden"
          aria-label="Open navigation menu"
        >
          <Menu className="size-5" />
        </button>
        <Breadcrumb crumbs={crumbs} />
      </div>

      <div className="hidden items-center gap-2 md:flex">
        <button
          type="button"
          onClick={() => setSearchOpen(true)}
          className="inline-flex h-9 items-center gap-2 rounded-md border bg-background px-3 text-xs text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
          aria-label="Search tickers"
        >
          <Search className="size-3.5" />
          <span>Search</span>
          <kbd className="ml-4 rounded border bg-muted px-1.5 py-0.5 text-[10px] font-medium text-muted-foreground">
            ⌘K
          </kbd>
        </button>
      </div>

      <SearchPalette
        open={searchOpen}
        onClose={() => setSearchOpen(false)}
        tickers={tickers}
      />
    </header>
  );
}

function SearchPalette({
  open,
  onClose,
  tickers,
}: {
  open: boolean;
  onClose: () => void;
  tickers: TickerSummary[];
}) {
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [activeIdx, setActiveIdx] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLUListElement>(null);

  const results = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return tickers.slice(0, 12);
    return tickers
      .filter(
        (t) =>
          t.symbol.toLowerCase().includes(q) ||
          t.name.toLowerCase().includes(q),
      )
      .slice(0, 20);
  }, [query, tickers]);

  useEffect(() => {
    if (open) {
      setQuery("");
      setActiveIdx(0);
      requestAnimationFrame(() => inputRef.current?.focus());
    }
  }, [open]);

  useEffect(() => {
    setActiveIdx(0);
  }, [query]);

  const go = useCallback(
    (symbol: string) => {
      router.push(`/${symbol}`);
      onClose();
    },
    [router, onClose],
  );

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        onClose();
      } else if (e.key === "ArrowDown") {
        e.preventDefault();
        setActiveIdx((i) => Math.min(i + 1, Math.max(results.length - 1, 0)));
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        setActiveIdx((i) => Math.max(i - 1, 0));
      } else if (e.key === "Enter") {
        const hit = results[activeIdx];
        if (hit) {
          e.preventDefault();
          go(hit.symbol);
        }
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, results, activeIdx, go, onClose]);

  useEffect(() => {
    const el = listRef.current?.querySelector<HTMLLIElement>(
      `[data-idx="${activeIdx}"]`,
    );
    el?.scrollIntoView({ block: "nearest" });
  }, [activeIdx]);

  if (!open) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Search tickers"
      className="fixed inset-0 z-50 flex items-start justify-center px-4 pt-[12vh]"
    >
      <button
        type="button"
        aria-label="Close search"
        onClick={onClose}
        className="absolute inset-0 bg-foreground/40 backdrop-blur-sm"
      />
      <div className="relative w-full max-w-lg overflow-hidden rounded-xl border bg-background shadow-2xl">
        <div className="flex items-center gap-2 border-b px-4">
          <Search className="size-4 shrink-0 text-muted-foreground" />
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search tickers…"
            className="h-12 w-full bg-transparent text-sm text-foreground placeholder:text-muted-foreground focus:outline-none"
            autoComplete="off"
            spellCheck={false}
          />
          <kbd className="hidden rounded border bg-muted px-1.5 py-0.5 text-[10px] font-medium text-muted-foreground sm:inline-block">
            Esc
          </kbd>
        </div>
        <ul
          ref={listRef}
          role="listbox"
          className="max-h-[50vh] overflow-y-auto py-1"
        >
          {results.length === 0 ? (
            <li className="px-4 py-6 text-center text-xs text-muted-foreground">
              No matches
            </li>
          ) : (
            results.map((t, i) => {
              const active = i === activeIdx;
              const dot = t.signal ? SIGNAL_DOT[t.signal] : "bg-muted-foreground/30";
              const up = (t.priceChangePct ?? 0) >= 0;
              return (
                <li
                  key={t.symbol}
                  data-idx={i}
                  role="option"
                  aria-selected={active}
                  onMouseEnter={() => setActiveIdx(i)}
                  onClick={() => go(t.symbol)}
                  className={cn(
                    "mx-1 flex h-11 cursor-pointer items-center gap-3 rounded-md px-3 text-sm",
                    active ? "bg-muted text-foreground" : "text-muted-foreground",
                  )}
                >
                  <span className={cn("size-1.5 shrink-0 rounded-full", dot)} aria-hidden />
                  <span className="num font-medium text-foreground">{t.symbol}</span>
                  {t.name && (
                    <span className="min-w-0 truncate text-xs text-muted-foreground">
                      {t.name}
                    </span>
                  )}
                  {t.priceChangePct != null && (
                    <span
                      className={cn(
                        "num ml-auto text-[11px]",
                        up ? "text-emerald-600" : "text-rose-600",
                      )}
                    >
                      {up ? "+" : ""}
                      {t.priceChangePct.toFixed(2)}%
                    </span>
                  )}
                </li>
              );
            })
          )}
        </ul>
      </div>
    </div>
  );
}

interface Crumb {
  label: string;
  href: string;
}

function buildCrumbs(pathname: string): Crumb[] {
  const segments = pathname.split("/").filter(Boolean);
  const crumbs: Crumb[] = [{ label: "Dashboard", href: "/" }];
  if (segments.length > 0) {
    const symbol = decodeURIComponent(segments[0]);
    crumbs.push({ label: symbol, href: `/${symbol}` });
  }
  return crumbs;
}

function Breadcrumb({ crumbs }: { crumbs: Crumb[] }) {
  return (
    <nav aria-label="Breadcrumb" className="min-w-0">
      <ol className="flex min-w-0 items-center gap-1.5 text-sm">
        {crumbs.map((c, i) => {
          const isLast = i === crumbs.length - 1;
          return (
            <Fragment key={c.href}>
              {i > 0 && (
                <li aria-hidden>
                  <ChevronRight className="size-3.5 text-muted-foreground/60" />
                </li>
              )}
              <li className={cn("min-w-0", isLast && "truncate")}>
                {isLast ? (
                  <span className="truncate font-medium text-foreground">
                    {c.label}
                  </span>
                ) : (
                  <Link
                    href={c.href}
                    className="text-muted-foreground transition-colors hover:text-foreground"
                  >
                    {c.label}
                  </Link>
                )}
              </li>
            </Fragment>
          );
        })}
      </ol>
    </nav>
  );
}
