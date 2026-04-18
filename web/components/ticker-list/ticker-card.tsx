import Link from "next/link";
import { ArrowUpRight } from "lucide-react";
import { SignalBadge } from "@/components/briefing/signal-badge";
import { fmtCurrency, fmtSignedPercent } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { TickerSummary } from "@/lib/types";

export function TickerCard({ t, index }: { t: TickerSummary; index?: number }) {
  const up = (t.priceChangePct ?? 0) >= 0;
  const conviction = t.conviction ?? 0;
  const convictionPct = Math.min(Math.abs(conviction) * 100, 100);
  const convictionTone =
    conviction > 0.15 ? "bg-emerald-400" : conviction < -0.15 ? "bg-rose-400" : "bg-zinc-400/70";

  return (
    <Link href={`/${t.symbol}`} className="group relative block focus:outline-none">
      <article
        className={cn(
          "relative h-full overflow-hidden rounded-sm border hairline bg-card/40 p-5 transition-all duration-300",
          "group-hover:-translate-y-0.5 group-hover:border-primary/50 group-hover:bg-card/70 group-hover:shadow-[0_10px_40px_-16px] group-hover:shadow-primary/40",
          "group-focus-visible:ring-2 group-focus-visible:ring-ring",
        )}
      >
        {/* corner marker */}
        <span className="absolute left-0 top-0 h-px w-10 bg-primary/70" aria-hidden />
        <span className="absolute left-0 top-0 h-10 w-px bg-primary/70" aria-hidden />

        <header className="flex items-start justify-between gap-3">
          <div className="flex items-baseline gap-3">
            {index != null && (
              <span className="num text-[10px] uppercase tracking-[0.22em] text-muted-foreground/60">
                {String(index).padStart(2, "0")}
              </span>
            )}
            <span className="num text-xl font-semibold tracking-tight">{t.symbol}</span>
            <span className="rounded-sm border hairline px-1.5 py-0.5 text-[9px] uppercase tracking-[0.18em] text-muted-foreground">
              {t.market}
            </span>
          </div>
          <ArrowUpRight className="size-4 text-muted-foreground/40 transition-all duration-300 group-hover:-translate-y-0.5 group-hover:translate-x-0.5 group-hover:text-primary" />
        </header>

        <div className="mt-1.5 truncate text-sm text-muted-foreground">{t.name}</div>

        <div className="mt-6 flex items-end justify-between gap-3">
          <div>
            <div className="num text-2xl font-semibold leading-none tracking-tight">
              {fmtCurrency(t.price, t.currency)}
            </div>
            {t.priceChangePct != null && (
              <div
                className={cn(
                  "num mt-2 text-xs",
                  up ? "text-emerald-400" : "text-rose-400",
                )}
              >
                {up ? "▲" : "▼"} {fmtSignedPercent(t.priceChangePct)}{" "}
                <span className="text-muted-foreground/70">session</span>
              </div>
            )}
          </div>
          {t.signal && <SignalBadge signal={t.signal} size="sm" />}
        </div>

        {t.conviction != null && (
          <div className="mt-5">
            <div className="mb-1.5 flex items-center justify-between text-[10px] uppercase tracking-[0.2em] text-muted-foreground/70">
              <span>Conviction</span>
              <span className="num text-foreground/80">
                {conviction >= 0 ? "+" : ""}
                {conviction.toFixed(2)}
              </span>
            </div>
            <div className="relative h-[3px] w-full overflow-hidden rounded-full bg-muted">
              <span className="absolute left-1/2 top-0 h-full w-px bg-border" aria-hidden />
              <span
                className={cn("absolute top-0 h-full rounded-full", convictionTone)}
                style={{
                  left: conviction >= 0 ? "50%" : `${50 - convictionPct / 2}%`,
                  width: `${convictionPct / 2}%`,
                }}
              />
            </div>
          </div>
        )}

        {t.sector && (
          <footer className="mt-5 flex items-center justify-between border-t hairline pt-3 text-[10px] uppercase tracking-[0.18em] text-muted-foreground/70">
            <span className="truncate">{t.sector}</span>
            <span className="display italic tracking-normal text-muted-foreground/50">
              read →
            </span>
          </footer>
        )}
      </article>
    </Link>
  );
}
