import Link from "next/link";
import { SignalBadge } from "@/components/briefing/signal-badge";
import { fmtCurrency, fmtSignedPercent } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { TickerSummary } from "@/lib/types";

export function TickerCard({ t }: { t: TickerSummary; index?: number }) {
  const up = (t.priceChangePct ?? 0) >= 0;
  const conviction = t.conviction ?? 0;
  const convictionPct = Math.min(Math.abs(conviction) * 100, 100);
  const convictionTone =
    conviction > 0.15
      ? "bg-emerald-500"
      : conviction < -0.15
        ? "bg-rose-500"
        : "bg-zinc-400";

  return (
    <Link href={`/${t.symbol}`} className="group block focus:outline-none">
      <article
        className={cn(
          "flex h-full flex-col gap-4 rounded-xl border bg-card p-5 transition-all duration-200",
          "group-hover:-translate-y-0.5 group-hover:border-foreground/20 group-hover:shadow-[0_6px_24px_-12px_rgba(0,0,0,0.12)]",
          "group-focus-visible:ring-2 group-focus-visible:ring-ring group-focus-visible:ring-offset-2",
        )}
      >
        <header className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <span className="num text-base font-semibold tracking-tight text-foreground">
                {t.symbol}
              </span>
              <span className="rounded-md bg-muted px-1.5 py-0.5 text-[10px] font-medium text-muted-foreground">
                {t.market}
              </span>
            </div>
            <p className="mt-1 truncate text-xs text-muted-foreground">{t.name}</p>
          </div>
          {t.signal && <SignalBadge signal={t.signal} size="sm" />}
        </header>

        <div className="flex items-end justify-between gap-3">
          <div>
            <div className="num text-xl font-semibold tracking-tight text-foreground">
              {fmtCurrency(t.price, t.currency)}
            </div>
            {t.priceChangePct != null && (
              <div
                className={cn(
                  "num mt-1 text-xs font-medium",
                  up ? "text-emerald-600" : "text-rose-600",
                )}
              >
                {up ? "+" : ""}
                {fmtSignedPercent(t.priceChangePct)}
              </div>
            )}
          </div>
          {t.conviction != null && (
            <div className="min-w-[110px] text-right">
              <div className="mb-1 text-[10px] font-medium text-muted-foreground">
                Conviction
              </div>
              <div className="relative ml-auto h-1 w-24 overflow-hidden rounded-full bg-muted">
                <span className="absolute left-1/2 top-0 h-full w-px bg-border" aria-hidden />
                <span
                  className={cn("absolute top-0 h-full rounded-full", convictionTone)}
                  style={{
                    left: conviction >= 0 ? "50%" : `${50 - convictionPct / 2}%`,
                    width: `${convictionPct / 2}%`,
                  }}
                />
              </div>
              <div className="num mt-1 text-[11px] text-foreground/70">
                {conviction >= 0 ? "+" : ""}
                {conviction.toFixed(2)}
              </div>
            </div>
          )}
        </div>

        {t.sector && (
          <footer className="border-t pt-3 text-[11px] text-muted-foreground">
            <span className="truncate">{t.sector}</span>
          </footer>
        )}
      </article>
    </Link>
  );
}
