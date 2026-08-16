"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { ArrowUpRight, BookOpen, LayoutDashboard } from "lucide-react";
import { BookShape } from "@/components/consensus/book-shape";
import { NeedsALook } from "@/components/layout/needs-a-look";
import { cn } from "@/lib/utils";
import { getMyList } from "@/lib/client-storage";
import { signalShortLabel } from "@/lib/signal-display";
import type { TickerSummary } from "@/lib/types";

/** The drawer is only ever hidden below `lg`; above it the aside is pinned. */
const DESKTOP_QUERY = "(min-width: 1024px)";

/** Caps that keep the rail inside one viewport. Overflow goes to the screener. */
const MY_LIST_MAX = 5;

export function Sidebar({
  tickers,
  open,
  onClose,
}: {
  tickers: TickerSummary[];
  open: boolean;
  onClose: () => void;
}) {
  const [mounted, setMounted] = useState(false);
  const [myListIds, setMyListIds] = useState<string[]>([]);
  // Assume desktop until proven otherwise so the server-rendered nav is never
  // delivered inert; the effect corrects it on the first client frame.
  const [isDesktop, setIsDesktop] = useState(true);

  useEffect(() => {
    function refresh() {
      setMyListIds(getMyList());
    }
    setMounted(true);
    refresh();
    window.addEventListener("mylist-change", refresh);
    return () => window.removeEventListener("mylist-change", refresh);
  }, []);

  useEffect(() => {
    const mq = window.matchMedia(DESKTOP_QUERY);
    const sync = () => setIsDesktop(mq.matches);
    sync();
    mq.addEventListener("change", sync);
    return () => mq.removeEventListener("change", sync);
  }, []);

  const tickerMap = Object.fromEntries(tickers.map((t) => [t.symbol, t]));

  const myListTickers = mounted
    ? myListIds.map((id) => tickerMap[id]).filter(Boolean)
    : [];

  // Off-screen but still in the DOM: without `inert` the tab order walks into a
  // nav the user cannot see.
  const offscreen = !isDesktop && !open;

  return (
    <aside
      inert={offscreen}
      className={cn(
        "fixed inset-y-0 left-0 z-50 flex h-dvh w-72 flex-col border-r bg-background transition-transform duration-200 ease-out",
        // Pinned to the viewport, never taller than it. As a plain static flex
        // child the aside stretched to the *page* height (4964px on a long
        // ticker page), which stranded everything below the nav far off-screen.
        "lg:sticky lg:top-0 lg:h-dvh lg:w-64 lg:shrink-0 lg:translate-x-0",
        open ? "translate-x-0" : "-translate-x-full lg:translate-x-0",
      )}
      aria-label="Primary navigation"
    >
      <div className="flex h-topbar shrink-0 items-center gap-2.5 border-b px-5">
        <span
          className="grid size-8 shrink-0 place-items-center rounded border border-ink text-ink"
          aria-hidden
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
            <line x1="4" y1="12" x2="20" y2="12" stroke="currentColor" strokeOpacity="0.45" strokeWidth="1.5" strokeLinecap="round" />
            <line x1="12" y1="8.5" x2="12" y2="15.5" stroke="currentColor" strokeOpacity="0.45" strokeWidth="1.5" strokeLinecap="round" />
            <circle cx="15.5" cy="12" r="2.5" fill="currentColor" />
          </svg>
        </span>
        <div className="min-w-0">
          <div className="text-sm font-semibold leading-none tracking-[-0.02em] text-ink [font-stretch:125%]">
            Desk
          </div>
          <div className="mt-1 text-micro text-graphite">Briefings</div>
        </div>
      </div>

      {/* Every list below is capped so the rail fits one viewport without a
          scrollbar. Only the mobile drawer may scroll, and only on short
          phones — on desktop nothing here overflows. */}
      <nav className="min-h-0 flex-1 overflow-y-auto px-3 py-4 text-sm lg:overflow-visible">
        <Section label="Overview">
          <NavItem href="/" icon={LayoutDashboard} onNavigate={onClose}>
            Screener
          </NavItem>
          <NavItem href="/about" icon={BookOpen} onNavigate={onClose}>
            How it works
          </NavItem>
        </Section>

        <Section
          label="My list"
          count={myListTickers.length || undefined}
          more={
            myListTickers.length > MY_LIST_MAX
              ? { count: myListTickers.length - MY_LIST_MAX, href: "/?starred=1" }
              : undefined
          }
          onNavigate={onClose}
        >
          {!mounted || myListTickers.length === 0 ? (
            <p className="px-3 py-2 text-micro text-graphite">
              Star any ticker to pin it here.
            </p>
          ) : (
            myListTickers
              .slice(0, MY_LIST_MAX)
              .map((t) => <TickerRow key={t.symbol} t={t} onNavigate={onClose} />)
          )}
        </Section>

        <NeedsALook tickers={tickers} onNavigate={onClose} max={3} />
      </nav>

      {/* Least critical of the three, so it is what gives way on a short
          window — better than forcing the whole rail to scroll. */}
      <div className="hidden shrink-0 border-t [@media(min-height:800px)]:block">
        <BookShape tickers={tickers} />
      </div>

      <div className="shrink-0 border-t px-5 py-4">
        <Link
          href="/"
          onClick={onClose}
          className="text-micro text-graphite transition-colors hover:text-action"
        >
          Browse all {tickers.length} tickers →
        </Link>
      </div>
    </aside>
  );
}

function Section({
  label,
  count,
  more,
  onNavigate,
  children,
}: {
  label: string;
  count?: number;
  /** Shown when the list was truncated to keep the rail within one viewport. */
  more?: { count: number; href: string };
  onNavigate?: () => void;
  children: React.ReactNode;
}) {
  return (
    <div className="mb-5 last:mb-0">
      <div className="mb-1 flex items-center justify-between px-3">
        <span className="eyebrow">{label}</span>
        {count != null && count > 0 && (
          <span className="num rounded bg-muted px-1.5 py-0.5 text-mini text-graphite">
            {count}
          </span>
        )}
      </div>
      <div className="space-y-0.5">{children}</div>
      {more && (
        <Link
          href={more.href}
          onClick={onNavigate}
          className="mt-1 block px-3 text-mini text-graphite transition-colors hover:text-action"
        >
          {more.count} more →
        </Link>
      )}
    </div>
  );
}

function NavItem({
  href,
  icon: Icon,
  external,
  onNavigate,
  children,
}: {
  href: string;
  icon: React.ComponentType<{ className?: string }>;
  external?: boolean;
  onNavigate?: () => void;
  children: React.ReactNode;
}) {
  const pathname = usePathname();
  const active = !external && pathname === href;
  const cls = cn(
    "group relative flex h-9 items-center gap-2.5 rounded px-3 text-sm transition-colors",
    active
      ? "bg-action/10 font-medium text-action"
      : "text-graphite hover:bg-secondary hover:text-action",
  );
  const content = (
    <>
      {active && (
        <span
          className="absolute -left-3 top-1/2 h-4 w-0.5 -translate-y-1/2 rounded-full bg-action"
          aria-hidden
        />
      )}
      <Icon className="size-4 shrink-0" />
      <span className="truncate">{children}</span>
      {external && <ArrowUpRight className="ml-auto size-3 text-graphite" />}
    </>
  );
  if (external) {
    return (
      <a href={href} target="_blank" rel="noreferrer" onClick={onNavigate} className={cls}>
        {content}
      </a>
    );
  }
  return (
    <Link href={href} onClick={onNavigate} className={cls}>
      {content}
    </Link>
  );
}

/** Fill colour for the signal dot. Neutral and un-briefed stay graphite. */
function signalDotTone(signal: TickerSummary["signal"]): string {
  if (signal === "strong_buy" || signal === "buy") return "bg-bull";
  if (signal === "strong_sell" || signal === "sell") return "bg-bear";
  return "bg-graphite";
}

/** Direction colour for a signed number. Zero counts as up, matching its sign. */
function numberTone(n: number): string {
  return n >= 0 ? "text-bull" : "text-bear";
}

/**
 * `metric` decides which number trails the row. The Top conviction list is
 * ranked by conviction, so showing a price change there put the signal glyph
 * and the number in open disagreement on most rows.
 */
function TickerRow({
  t,
  onNavigate,
  metric = "price",
}: {
  t: TickerSummary;
  onNavigate?: () => void;
  metric?: "price" | "conviction";
}) {
  const pathname = usePathname();
  const active = pathname === `/${t.symbol}`;
  const showConviction = metric === "conviction" && t.conviction != null;
  return (
    <Link
      href={`/${t.symbol}`}
      onClick={onNavigate}
      aria-current={active ? "page" : undefined}
      className={cn(
        "group flex h-10 items-center gap-2.5 rounded px-3 transition-colors",
        active
          ? "bg-action/10 font-medium text-action"
          : "text-graphite hover:bg-secondary hover:text-action",
      )}
    >
      {/* A dot, not an arrow. The trailing number carries its own ▲/▼, and two
          arrows per row read as a contradiction whenever the desk is bullish on
          a name that happens to be down today — which is the whole buy-the-dip
          case. Dot = standing verdict, arrow = today's move. */}
      <span
        className={cn(
          "size-1.5 shrink-0 rounded-full",
          signalDotTone(t.signal),
        )}
        aria-hidden
      />
      <span className="sr-only">{signalShortLabel(t.signal)}.</span>
      <div className="min-w-0 flex-1">
        <div className="num truncate text-xs font-medium text-ink">{t.symbol}</div>
      </div>
      {showConviction ? (
        <span className={cn("num text-micro", numberTone(t.conviction!))}>
          {t.conviction! >= 0 ? "+" : ""}
          {t.conviction!.toFixed(2)}
          <span className="sr-only"> conviction</span>
        </span>
      ) : (
        t.priceChangePct != null && (
          <span className={cn("num text-micro", numberTone(t.priceChangePct))}>
            <span aria-hidden>{t.priceChangePct >= 0 ? "▲" : "▼"}</span>{" "}
            {t.priceChangePct >= 0 ? "+" : ""}
            {t.priceChangePct.toFixed(2)}%
            <span className="sr-only"> since the previous close</span>
          </span>
        )
      )}
    </Link>
  );
}
