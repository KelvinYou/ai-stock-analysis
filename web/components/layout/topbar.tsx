"use client";

import { Fragment } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { ChevronRight, Menu, Radio } from "lucide-react";
import { cn } from "@/lib/utils";
import type { TickerSummary } from "@/lib/types";

export function Topbar({
  tickers,
  onMenuClick,
}: {
  tickers: TickerSummary[];
  onMenuClick: () => void;
}) {
  const pathname = usePathname();
  const crumbs = buildCrumbs(pathname, tickers);
  const briefingCount = tickers.filter((t) => t.signal != null).length;
  const bullCount = tickers.filter(
    (t) => t.signal === "buy" || t.signal === "strong_buy",
  ).length;
  const bearCount = tickers.filter(
    (t) => t.signal === "sell" || t.signal === "strong_sell",
  ).length;

  return (
    <header className="sticky top-0 z-30 flex h-14 shrink-0 items-center justify-between gap-4 border-b hairline bg-background/75 px-5 backdrop-blur-xl md:px-10">
      <div className="flex min-w-0 items-center gap-3">
        <button
          type="button"
          onClick={onMenuClick}
          className="-ml-1 inline-flex size-9 items-center justify-center rounded-sm text-muted-foreground transition-colors hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring lg:hidden"
          aria-label="Open navigation menu"
        >
          <Menu className="size-5" />
        </button>
        <Breadcrumb crumbs={crumbs} />
      </div>

      {tickers.length > 0 && (
        <div className="hidden shrink-0 items-center gap-2 text-[11px] md:flex">
          <TickerChip tone="bull" count={bullCount} label="BULL" />
          <TickerChip tone="bear" count={bearCount} label="BEAR" />
          <TickerChip
            tone="muted"
            count={briefingCount}
            total={tickers.length}
            label="LIVE"
            pulse
          />
        </div>
      )}
    </header>
  );
}

function TickerChip({
  tone,
  count,
  total,
  label,
  pulse,
}: {
  tone: "bull" | "bear" | "muted";
  count: number;
  total?: number;
  label: string;
  pulse?: boolean;
}) {
  const cls =
    tone === "bull"
      ? "text-emerald-400/90 border-emerald-400/25"
      : tone === "bear"
        ? "text-rose-400/90 border-rose-400/25"
        : "text-muted-foreground border-border/60";
  return (
    <span
      className={cn(
        "inline-flex items-center gap-2 rounded-sm border bg-background/40 px-2.5 py-1 tracking-[0.18em]",
        cls,
      )}
    >
      {pulse && <Radio className="size-3 animate-pulse-soft" aria-hidden />}
      <span className="num text-foreground">
        {String(count).padStart(2, "0")}
        {total != null && <span className="text-muted-foreground">/{total}</span>}
      </span>
      <span className="text-[10px]">{label}</span>
    </span>
  );
}

interface Crumb {
  label: string;
  href: string;
}

function buildCrumbs(pathname: string, tickers: TickerSummary[]): Crumb[] {
  const segments = pathname.split("/").filter(Boolean);
  const crumbs: Crumb[] = [{ label: "Dashboard", href: "/" }];
  if (segments.length > 0) {
    const symbol = decodeURIComponent(segments[0]);
    const t = tickers.find((x) => x.symbol === symbol);
    crumbs.push({
      label: t ? `${symbol} · ${t.name}` : symbol,
      href: `/${symbol}`,
    });
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
                  <ChevronRight className="size-3.5 text-muted-foreground/50" />
                </li>
              )}
              <li className={cn("min-w-0", isLast && "truncate")}>
                {isLast ? (
                  <span className="display truncate text-base tracking-tight">
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
