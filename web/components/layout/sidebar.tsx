"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { ArrowUpRight, BookOpen, LayoutDashboard } from "lucide-react";
import { cn } from "@/lib/utils";
import { getMyList, getRecentlyViewed } from "@/lib/client-storage";
import type { Signal, TickerSummary } from "@/lib/types";

const SIGNAL_DOT: Record<Signal, string> = {
  strong_buy: "bg-emerald-500",
  buy: "bg-emerald-500/70",
  neutral: "bg-zinc-400",
  sell: "bg-rose-500/70",
  strong_sell: "bg-rose-500",
};

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
  const [recentIds, setRecentIds] = useState<string[]>([]);

  useEffect(() => {
    function refresh() {
      setMyListIds(getMyList());
      setRecentIds(getRecentlyViewed());
    }
    setMounted(true);
    refresh();
    window.addEventListener("mylist-change", refresh);
    window.addEventListener("recent-change", refresh);
    return () => {
      window.removeEventListener("mylist-change", refresh);
      window.removeEventListener("recent-change", refresh);
    };
  }, []);

  const tickerMap = Object.fromEntries(tickers.map((t) => [t.symbol, t]));

  const topConviction = tickers
    .filter((t) => t.signal != null && t.conviction != null)
    .sort((a, b) => {
      const diff = Math.abs(b.conviction ?? 0) - Math.abs(a.conviction ?? 0);
      if (diff !== 0) return diff;
      return (a.signal === "strong_buy" || a.signal === "strong_sell" ? 0 : 1) -
        (b.signal === "strong_buy" || b.signal === "strong_sell" ? 0 : 1);
    })
    .filter((t) => t.signal === "strong_buy" || t.signal === "buy" ||
      t.signal === "strong_sell" || t.signal === "sell")
    .slice(0, 6);

  const myListTickers = mounted
    ? myListIds.map((id) => tickerMap[id]).filter(Boolean)
    : [];
  const recentTickers = mounted
    ? recentIds.map((id) => tickerMap[id]).filter(Boolean)
    : [];

  return (
    <aside
      className={cn(
        "fixed inset-y-0 left-0 z-50 flex h-dvh w-72 flex-col border-r bg-background transition-transform duration-200 ease-out",
        "lg:static lg:h-auto lg:w-64 lg:translate-x-0",
        open ? "translate-x-0" : "-translate-x-full lg:translate-x-0",
      )}
      aria-label="Primary navigation"
    >
      <div className="flex h-16 shrink-0 items-center gap-2.5 border-b px-5">
        <span
          className="grid size-8 shrink-0 place-items-center rounded-lg bg-brand text-brand-foreground"
          aria-hidden
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
            <line x1="4" y1="12" x2="20" y2="12" stroke="currentColor" strokeOpacity="0.45" strokeWidth="1.5" strokeLinecap="round" />
            <line x1="12" y1="8.5" x2="12" y2="15.5" stroke="currentColor" strokeOpacity="0.45" strokeWidth="1.5" strokeLinecap="round" />
            <circle cx="15.5" cy="12" r="2.5" fill="hsl(var(--bull))" />
          </svg>
        </span>
        <div className="min-w-0">
          <div className="text-sm font-semibold leading-none tracking-tight text-foreground">
            Desk
          </div>
          <div className="mt-1 text-[11px] text-muted-foreground">Briefings</div>
        </div>
      </div>

      <nav className="flex-1 overflow-y-auto px-3 py-4 text-sm">
        <Section label="Overview">
          <NavItem href="/" icon={LayoutDashboard} onNavigate={onClose}>
            Screener
          </NavItem>
          <NavItem href="/about" icon={BookOpen} onNavigate={onClose}>
            How it works
          </NavItem>
        </Section>

        <Section label="My list" count={myListTickers.length || undefined}>
          {!mounted || myListTickers.length === 0 ? (
            <p className="px-3 py-2 text-[11px] text-muted-foreground">
              Star any ticker to pin it here.
            </p>
          ) : (
            myListTickers.map((t) => (
              <TickerRow key={t.symbol} t={t} onNavigate={onClose} />
            ))
          )}
        </Section>

        {mounted && recentTickers.length > 0 && (
          <Section label="Recently viewed">
            {recentTickers.map((t) => (
              <TickerRow key={t.symbol} t={t} onNavigate={onClose} />
            ))}
          </Section>
        )}

        {topConviction.length > 0 && (
          <Section label="Top conviction">
            {topConviction.map((t) => (
              <TickerRow key={t.symbol} t={t} onNavigate={onClose} />
            ))}
          </Section>
        )}
      </nav>

      <div className="shrink-0 border-t px-5 py-4">
        <Link
          href="/"
          onClick={onClose}
          className="text-[11px] text-muted-foreground transition-colors hover:text-brand"
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
  children,
}: {
  label: string;
  count?: number;
  children: React.ReactNode;
}) {
  return (
    <div className="mb-5 last:mb-0">
      <div className="mb-1 flex items-center justify-between px-3 text-[11px] font-medium text-muted-foreground">
        <span>{label}</span>
        {count != null && count > 0 && (
          <span className="num rounded-md bg-muted px-1.5 py-0.5 text-[10px] text-foreground/80">
            {count}
          </span>
        )}
      </div>
      <div className="space-y-0.5">{children}</div>
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
    "group relative flex h-9 items-center gap-2.5 rounded-md px-3 text-[13px] transition-colors",
    active
      ? "bg-brand/10 font-medium text-brand"
      : "text-muted-foreground hover:bg-muted/60 hover:text-foreground",
  );
  const content = (
    <>
      {active && (
        <span
          className="absolute -left-3 top-1/2 h-4 -translate-y-1/2 w-0.5 rounded-full bg-brand"
          aria-hidden
        />
      )}
      <Icon className="size-4 shrink-0" />
      <span className="truncate">{children}</span>
      {external && <ArrowUpRight className="ml-auto size-3 opacity-60" />}
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

function TickerRow({ t, onNavigate }: { t: TickerSummary; onNavigate?: () => void }) {
  const pathname = usePathname();
  const active = pathname === `/${t.symbol}`;
  const dot = t.signal ? SIGNAL_DOT[t.signal] : "bg-muted-foreground/30";
  const up = (t.priceChangePct ?? 0) >= 0;
  return (
    <Link
      href={`/${t.symbol}`}
      onClick={onNavigate}
      aria-current={active ? "page" : undefined}
      className={cn(
        "group flex h-10 items-center gap-2.5 rounded-md px-3 transition-colors",
        active
          ? "bg-brand/10 font-medium text-foreground"
          : "text-muted-foreground hover:bg-muted/60 hover:text-foreground",
      )}
    >
      <span className={cn("size-1.5 shrink-0 rounded-full", dot)} aria-hidden />
      <div className="min-w-0 flex-1">
        <div className="num truncate text-[12.5px] font-medium text-foreground">
          {t.symbol}
        </div>
      </div>
      {t.priceChangePct != null && (
        <span
          className={cn(
            "num text-[11px]",
            up ? "text-emerald-600" : "text-rose-600",
          )}
        >
          {up ? "+" : ""}
          {t.priceChangePct.toFixed(2)}%
        </span>
      )}
    </Link>
  );
}
