import Link from "next/link";
import { SignalBadge } from "@/components/briefing/signal-badge";
import { StarButton } from "@/components/ticker-list/star-button";
import { fmtCurrency, fmtSignedPercent } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { TickerSummary } from "@/lib/types";

/** −1…+1 conviction fills at most half the track, out from the centre tick. */
const CONVICTION_MAX = 1;

export function TickerCard({ t }: { t: TickerSummary; index?: number }) {
  const up = (t.priceChangePct ?? 0) >= 0;
  const conviction = t.conviction ?? 0;
  const halfWidthPct = (Math.min(Math.abs(conviction), CONVICTION_MAX) / CONVICTION_MAX) * 50;

  return (
    // The card is the landmark; the symbol link stretches over it so the whole
    // card is clickable without burying <header>/<footer> inside an anchor.
    <article
      className={cn(
        "group relative flex h-full flex-col gap-4 rounded-lg border bg-card p-5",
        "transition-colors duration-200 hover:border-ink focus-within:border-ink",
      )}
    >
      <header className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <Link
              href={`/${t.symbol}`}
              className="num text-base font-semibold tracking-tight text-ink after:absolute after:inset-0 after:content-['']"
            >
              {t.symbol}
            </Link>
            <span className="rounded bg-muted px-1.5 py-0.5 text-mini font-medium text-graphite">
              {t.market}
            </span>
            {t.group === "tracked" && (
              <span className="rounded bg-ink px-1.5 py-0.5 text-mini font-semibold uppercase tracking-[0.07em] text-background">
                Tracked
              </span>
            )}
          </div>
          <p className="mt-1 truncate text-xs text-graphite">{t.name}</p>
        </div>
        <div className="relative z-10 flex items-center gap-1">
          <StarButton symbol={t.symbol} />
          {t.signal ? (
            <SignalBadge signal={t.signal} size="sm" />
          ) : (
            <span className="inline-flex items-center rounded-full border px-2 py-0.5 text-mini font-medium text-graphite">
              Not briefed yet
            </span>
          )}
        </div>
      </header>

      <div className="flex items-end justify-between gap-3">
        <div>
          <div className="num text-xl font-semibold tracking-tight text-ink">
            {fmtCurrency(t.price, t.currency)}
          </div>
          {t.priceChangePct != null && (
            <div
              className={cn(
                "num mt-1 text-xs font-medium",
                up ? "text-bull" : "text-bear",
              )}
            >
              {/* The glyph stays: colour is the second cue here, never the first. */}
              <span aria-hidden className="mr-1">
                {up ? "▲" : "▼"}
              </span>
              <span>{fmtSignedPercent(t.priceChangePct)}</span>
              <span className="sr-only"> since the previous close</span>
            </div>
          )}
        </div>
        {t.conviction != null && (
          <div className="min-w-[110px] text-right">
            <div className="eyebrow mb-1">Conviction</div>
            <div
              role="progressbar"
              aria-valuenow={Number(conviction.toFixed(2))}
              aria-valuemin={-CONVICTION_MAX}
              aria-valuemax={CONVICTION_MAX}
              aria-label={`Conviction ${conviction.toFixed(2)} on a scale from −1 (max bearish) to +1 (max bullish)`}
              className="relative ml-auto h-1 w-24 overflow-hidden rounded-full bg-muted"
            >
              <span className="absolute left-1/2 top-0 h-full w-px bg-rule" aria-hidden />
              <span
                className={cn(
                  "absolute top-0 h-full rounded-full",
                  conviction > 0 ? "bg-bull" : conviction < 0 ? "bg-bear" : "bg-graphite",
                )}
                aria-hidden
                style={{
                  left: conviction >= 0 ? "50%" : `${50 - halfWidthPct}%`,
                  width: `${halfWidthPct}%`,
                }}
              />
            </div>
            <div className="num mt-1 text-micro text-graphite">
              {conviction >= 0 ? "+" : ""}
              {conviction.toFixed(2)}
            </div>
          </div>
        )}
      </div>

      {t.sector && (
        <footer className="mt-auto border-t pt-3 text-micro text-graphite">
          <span className="truncate">{t.sector}</span>
        </footer>
      )}
    </article>
  );
}
