"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { ArrowUpRight, LayoutDashboard, LineChart } from "lucide-react";
import { cn } from "@/lib/utils";
import type { Signal, TickerSummary } from "@/lib/types";

const SIGNAL_DOT: Record<Signal, string> = {
  strong_buy: "bg-emerald-400 shadow-[0_0_10px] shadow-emerald-400/60",
  buy: "bg-emerald-400/80",
  neutral: "bg-zinc-400/50",
  sell: "bg-rose-400/80",
  strong_sell: "bg-rose-400 shadow-[0_0_10px] shadow-rose-400/60",
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
  return (
    <aside
      className={cn(
        "fixed inset-y-0 left-0 z-50 flex h-dvh w-72 flex-col border-r hairline bg-background/95 backdrop-blur-xl transition-transform duration-300 ease-out",
        "lg:static lg:h-auto lg:w-64 lg:translate-x-0 lg:bg-background/40",
        open ? "translate-x-0" : "-translate-x-full lg:translate-x-0",
      )}
      aria-label="Primary navigation"
    >
      <div className="flex h-16 shrink-0 items-center gap-3 border-b hairline px-5">
        <span className="relative grid size-9 place-items-center rounded-sm bg-primary text-primary-foreground">
          <LineChart className="size-4" strokeWidth={2.5} />
          <span
            className="absolute -bottom-1 -right-1 size-2 rounded-full bg-emerald-400 ring-2 ring-background animate-pulse-soft"
            aria-hidden
          />
        </span>
        <div className="min-w-0">
          <div className="display text-lg leading-none tracking-tight">
            The<span className="italic text-primary"> Desk</span>
          </div>
          <div className="mt-1 text-[10px] uppercase tracking-[0.22em] text-muted-foreground/80">
            Briefings · v1
          </div>
        </div>
      </div>

      <nav className="flex-1 overflow-y-auto px-3 py-5 text-sm">
        <Section label="Overview">
          <NavItem href="/" icon={LayoutDashboard} onNavigate={onClose}>
            Dashboard
          </NavItem>
        </Section>

        <Section label="Watchlist" count={tickers.length}>
          {tickers.length === 0 ? (
            <p className="px-3 py-2 text-xs text-muted-foreground">No tickers yet</p>
          ) : (
            tickers.map((t) => <TickerRow key={t.symbol} t={t} onNavigate={onClose} />)
          )}
        </Section>

        <Section label="Elsewhere">
          <NavItem
            href="https://github.com/anthropics/claude-code"
            icon={ArrowUpRight}
            external
            onNavigate={onClose}
          >
            GitHub
          </NavItem>
        </Section>
      </nav>

      <div className="shrink-0 border-t hairline p-5">
        <blockquote className="display text-xs leading-snug text-muted-foreground/80">
          <span className="text-primary">&ldquo;</span>Four agents, one debate, one briefing.
          <span className="text-primary">&rdquo;</span>
        </blockquote>
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
    <div className="mb-7 last:mb-0">
      <div className="mb-2 flex items-center justify-between px-3 text-[10px] uppercase tracking-[0.22em] text-muted-foreground/70">
        <span>{label}</span>
        {count != null && (
          <span className="num rounded-sm bg-muted/60 px-1.5 py-0.5 text-[10px] text-foreground/80">
            {String(count).padStart(2, "0")}
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
    "group relative flex h-10 items-center gap-3 rounded-sm px-3 text-sm transition-colors",
    active
      ? "bg-muted/70 text-foreground"
      : "text-muted-foreground hover:bg-muted/40 hover:text-foreground",
  );
  const content = (
    <>
      {active && (
        <span
          className="absolute -left-3 top-1/2 h-5 w-[3px] -translate-y-1/2 rounded-r bg-primary"
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
        "group relative flex h-11 items-center gap-3 rounded-sm px-3 transition-colors",
        active
          ? "bg-muted/70 text-foreground"
          : "text-muted-foreground hover:bg-muted/40 hover:text-foreground",
      )}
    >
      {active && (
        <span
          className="absolute -left-3 top-1/2 h-6 w-[3px] -translate-y-1/2 rounded-r bg-primary"
          aria-hidden
        />
      )}
      <span className={cn("size-2 shrink-0 rounded-full transition-shadow", dot)} aria-hidden />
      <div className="min-w-0 flex-1">
        <div className="num text-[13px] font-semibold tracking-tight text-foreground">
          {t.symbol}
        </div>
        <div className="truncate text-[10px] uppercase tracking-[0.18em] text-muted-foreground/70">
          {t.market}
        </div>
      </div>
      {t.priceChangePct != null && (
        <span
          className={cn(
            "num text-[11px] tabular-nums",
            up ? "text-emerald-400/90" : "text-rose-400/90",
          )}
        >
          {up ? "▲" : "▼"}
          {Math.abs(t.priceChangePct).toFixed(2)}
        </span>
      )}
    </Link>
  );
}
