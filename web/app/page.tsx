import { TickerCard } from "@/components/ticker-list/ticker-card";
import { EmptyState } from "@/components/shared/empty-state";
import { listTickerSummaries } from "@/lib/data";

export const revalidate = 0;

export default async function HomePage() {
  const tickers = await listTickerSummaries();

  if (tickers.length === 0) {
    return <EmptyState />;
  }

  const bullish = tickers.filter(
    (t) => t.signal === "buy" || t.signal === "strong_buy",
  ).length;
  const bearish = tickers.filter(
    (t) => t.signal === "sell" || t.signal === "strong_sell",
  ).length;
  const avgConviction =
    tickers.filter((t) => t.conviction != null).length > 0
      ? tickers.reduce((s, t) => s + (t.conviction ?? 0), 0) /
        tickers.filter((t) => t.conviction != null).length
      : 0;
  const today = new Date().toLocaleDateString("en-US", {
    weekday: "long",
    month: "long",
    day: "numeric",
    year: "numeric",
  });

  return (
    <div className="space-y-14">
      {/* Masthead */}
      <section className="rise-in">
        <div className="mb-5 flex items-center justify-between gap-4 text-[10px] uppercase tracking-[0.28em] text-muted-foreground/80">
          <span>Vol. 01 · No. {String(tickers.length).padStart(3, "0")}</span>
          <span className="hidden sm:inline">{today}</span>
          <span className="num text-primary">Edition · Daily</span>
        </div>
        <div className="ruler mb-6" />
        <div className="grid gap-8 md:grid-cols-[1.3fr_1fr] md:items-end">
          <div>
            <h1 className="display text-[clamp(2.75rem,7vw,5.5rem)] font-light leading-[0.95] tracking-tight">
              The briefing, <br />
              <span className="italic text-primary">condensed.</span>
            </h1>
            <p className="mt-6 max-w-xl text-[15px] leading-relaxed text-muted-foreground">
              Four specialist agents — fundamentals, technicals, sentiment, macro — read the tape
              independently. A bull and bear researcher debate across three rounds. A synthesizer
              arbitrates. A risk checker calibrates.
            </p>
          </div>

          <div className="grid grid-cols-3 gap-px overflow-hidden rounded-sm border hairline bg-border/40">
            <PulseStat
              label="Coverage"
              value={String(tickers.length).padStart(2, "0")}
              hint="tickers live"
            />
            <PulseStat
              label="Bull · Bear"
              value={`${bullish}·${bearish}`}
              hint="signals split"
              tone={bullish >= bearish ? "bull" : "bear"}
            />
            <PulseStat
              label="Conviction"
              value={`${avgConviction >= 0 ? "+" : ""}${avgConviction.toFixed(2)}`}
              hint="mean score"
              tone={avgConviction > 0.15 ? "bull" : avgConviction < -0.15 ? "bear" : "muted"}
            />
          </div>
        </div>
      </section>

      {/* Grid */}
      <section aria-labelledby="all-tickers">
        <header className="mb-6 flex items-end justify-between gap-4 border-b hairline pb-3">
          <div className="flex items-baseline gap-4">
            <span className="num text-xs uppercase tracking-[0.24em] text-primary">§ 01</span>
            <h2 id="all-tickers" className="display text-2xl tracking-tight md:text-3xl">
              Coverage universe
            </h2>
          </div>
          <span className="hidden text-[10px] uppercase tracking-[0.22em] text-muted-foreground sm:inline">
            Sorted alphabetically
          </span>
        </header>
        <div
          aria-label="Ticker list"
          className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-2 xl:grid-cols-3"
        >
          {tickers.map((t, i) => (
            <div
              key={t.symbol}
              className="rise-in"
              style={{ animationDelay: `${Math.min(i * 60, 400)}ms` }}
            >
              <TickerCard t={t} index={i + 1} />
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}

function PulseStat({
  label,
  value,
  hint,
  tone,
}: {
  label: string;
  value: string;
  hint: string;
  tone?: "bull" | "bear" | "muted";
}) {
  const tint =
    tone === "bull"
      ? "text-emerald-400"
      : tone === "bear"
        ? "text-rose-400"
        : "text-foreground";
  return (
    <div className="flex flex-col justify-between gap-3 bg-background/80 px-4 py-4">
      <span className="text-[10px] uppercase tracking-[0.22em] text-muted-foreground/80">
        {label}
      </span>
      <span className={`num text-3xl font-semibold leading-none tracking-tight ${tint}`}>
        {value}
      </span>
      <span className="text-[10px] uppercase tracking-[0.18em] text-muted-foreground/70">
        {hint}
      </span>
    </div>
  );
}
