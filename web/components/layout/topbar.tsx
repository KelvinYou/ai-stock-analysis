"use client";

import { Fragment, useCallback, useEffect, useId, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import Link from "next/link";
import { useRouter, usePathname } from "next/navigation";
import { ChevronRight, Menu, Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ThemeToggle } from "@/components/shared/theme-toggle";
import { cn } from "@/lib/utils";
import { signalGlyph, signalShortLabel } from "@/lib/signal-display";
import type { TickerSummary } from "@/lib/types";

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
  const triggerRef = useRef<HTMLButtonElement>(null);

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
    <header className="sticky top-0 z-30 flex h-topbar shrink-0 items-center justify-between gap-4 border-b bg-background/80 px-5 backdrop-blur-md md:px-10">
      <div className="flex min-w-0 items-center gap-3">
        <Button
          variant="ghost"
          size="icon"
          onClick={onMenuClick}
          className="-ml-1 lg:hidden"
          aria-label="Open navigation menu"
        >
          <Menu className="size-5" />
        </Button>
        <Breadcrumb crumbs={crumbs} />
      </div>

      <div className="flex items-center gap-1">
        <ThemeToggle />
        <Button
          ref={triggerRef}
          variant="outline"
          size="sm"
          onClick={() => setSearchOpen(true)}
          className="hidden text-graphite hover:border-action hover:text-action md:inline-flex"
          aria-label="Search tickers"
        >
          <Search className="size-3.5" />
          <span>Search</span>
          <kbd className="num ml-4 rounded border bg-muted px-1.5 py-0.5 text-mini font-medium text-graphite">
            ⌘K
          </kbd>
        </Button>
      </div>

      <SearchPalette
        open={searchOpen}
        onClose={() => setSearchOpen(false)}
        tickers={tickers}
      />
    </header>
  );
}

const FOCUSABLE =
  'a[href], button:not([disabled]), input:not([disabled]), [tabindex]:not([tabindex="-1"])';

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
  const panelRef = useRef<HTMLDivElement>(null);
  const restoreRef = useRef<HTMLElement | null>(null);

  const baseId = useId();
  const inputId = `${baseId}-input`;
  const listboxId = `${baseId}-listbox`;
  const optionId = (i: number) => `${baseId}-option-${i}`;

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

  // A dialog that swallows focus has to give it back, or the keyboard user is
  // dropped at the top of the document every time they dismiss the palette.
  useEffect(() => {
    if (!open) return;
    restoreRef.current = document.activeElement as HTMLElement | null;
    return () => restoreRef.current?.focus?.();
  }, [open]);

  useEffect(() => {
    setActiveIdx(0);
  }, [query]);

  // Now that the overlay really covers the viewport, the page behind it must
  // stop scrolling under the wheel.
  useEffect(() => {
    if (!open) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = prev;
    };
  }, [open]);

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
      } else if (e.key === "Tab") {
        // aria-modal is a promise to assistive tech; without a trap the promise
        // is false the moment the user presses Tab.
        const nodes = panelRef.current?.querySelectorAll<HTMLElement>(FOCUSABLE);
        if (!nodes || nodes.length === 0) return;
        const first = nodes[0];
        const last = nodes[nodes.length - 1];
        const activeEl = document.activeElement;
        if (e.shiftKey && (activeEl === first || !panelRef.current?.contains(activeEl))) {
          e.preventDefault();
          last.focus();
        } else if (!e.shiftKey && activeEl === last) {
          e.preventDefault();
          first.focus();
        }
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

  // Portalled to <body> on purpose: the topbar carries `backdrop-blur`, and a
  // backdrop-filter makes that element the containing block for fixed-position
  // descendants — rendering in place pinned the overlay to the topbar strip
  // instead of the viewport.
  return createPortal(
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
        className="absolute inset-0 bg-ink/40 backdrop-blur-sm"
      />
      <div
        ref={panelRef}
        className="relative w-full max-w-lg overflow-hidden rounded-lg border bg-popover shadow-lg"
      >
        <div className="flex items-center gap-2 border-b px-4">
          <Search className="size-4 shrink-0 text-graphite" aria-hidden />
          <label htmlFor={inputId} className="sr-only">
            Search tickers by symbol or name
          </label>
          <input
            id={inputId}
            ref={inputRef}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search tickers…"
            role="combobox"
            aria-expanded
            aria-controls={listboxId}
            aria-autocomplete="list"
            aria-activedescendant={
              results.length > 0 ? optionId(activeIdx) : undefined
            }
            className="h-12 w-full bg-transparent text-sm text-ink outline-none placeholder:text-graphite"
            autoComplete="off"
            spellCheck={false}
          />
          <kbd className="hidden rounded border bg-muted px-1.5 py-0.5 text-mini font-medium text-graphite sm:inline-block">
            Esc
          </kbd>
        </div>
        <ul
          id={listboxId}
          ref={listRef}
          role="listbox"
          aria-label="Ticker results"
          className="max-h-[50vh] overflow-y-auto py-1"
        >
          {results.length === 0 ? (
            <li className="px-4 py-6 text-center text-xs text-graphite">
              No matches
            </li>
          ) : (
            results.map((t, i) => {
              const active = i === activeIdx;
              return (
                <li
                  key={t.symbol}
                  id={optionId(i)}
                  data-idx={i}
                  role="option"
                  aria-selected={active}
                  onMouseEnter={() => setActiveIdx(i)}
                  onClick={() => go(t.symbol)}
                  className={cn(
                    "mx-1 flex h-11 cursor-pointer items-center gap-3 rounded px-3 text-sm",
                    active ? "bg-action/10 text-action" : "text-graphite",
                  )}
                >
                  <span
                    className="w-4 shrink-0 text-center text-mini leading-none text-graphite"
                    aria-hidden
                  >
                    {signalGlyph(t.signal)}
                  </span>
                  <span className="sr-only">{signalShortLabel(t.signal)}.</span>
                  <span className="num font-medium text-ink">{t.symbol}</span>
                  {t.name && (
                    <span className="min-w-0 truncate text-xs text-graphite">
                      {t.name}
                    </span>
                  )}
                  {t.priceChangePct != null && (
                    <span className="num ml-auto text-micro text-graphite">
                      {t.priceChangePct >= 0 ? "+" : ""}
                      {t.priceChangePct.toFixed(2)}%
                    </span>
                  )}
                </li>
              );
            })
          )}
        </ul>
      </div>
    </div>,
    document.body,
  );
}

interface Crumb {
  label: string;
  href: string;
}

function buildCrumbs(pathname: string): Crumb[] {
  const segments = pathname.split("/").filter(Boolean);
  const crumbs: Crumb[] = [{ label: "Screener", href: "/" }];
  if (segments[0] === "about") return [...crumbs, { label: "How it works", href: "/about" }];
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
                  <ChevronRight className="size-3.5 text-graphite" />
                </li>
              )}
              <li className={cn("min-w-0", isLast && "truncate")}>
                {isLast ? (
                  <span className="truncate font-medium text-ink">{c.label}</span>
                ) : (
                  <Link
                    href={c.href}
                    className="text-graphite transition-colors hover:text-action"
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
