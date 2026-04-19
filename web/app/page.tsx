import Link from "next/link";
import { ArrowRight, TrendingUp, TrendingDown } from "lucide-react";
import { listTickerSummaries } from "@/lib/data";
import { SignalBadge } from "@/components/briefing/signal-badge";
import { fmtCurrency, fmtSignedPercent, signalLabel } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { TickerSummary } from "@/lib/types";

export const revalidate = 3600;

const AGENTS = [
  {
    step: "01",
    name: "Four analysts",
    desc: "Fundamentals, technicals, sentiment, and macro agents each read the tape independently and file a typed report with a signal and confidence score.",
  },
  {
    step: "02",
    name: "Adversarial debate",
    desc: "A bull researcher and a bear researcher argue N rounds, citing the analyst reports. Points of agreement, disagreement, and unresolved uncertainties are surfaced.",
  },
  {
    step: "03",
    name: "Synthesis",
    desc: "A synthesizer reads all four reports plus the debate and produces a final briefing: overall signal, conviction score, entry / stop / target levels.",
  },
];

export default async function LandingPage() {
  const tickers = await listTickerSummaries();

  const briefed = tickers.filter((t) => t.signal != null);
  const byConviction = [...briefed].sort(
    (a, b) => (b.conviction ?? 0) - (a.conviction ?? 0),
  );
  const topBuys = byConviction
    .filter((t) => t.signal === "strong_buy" || t.signal === "buy")
    .slice(0, 5);
  const topSells = [...briefed]
    .sort((a, b) => (a.conviction ?? 0) - (b.conviction ?? 0))
    .filter((t) => t.signal === "strong_sell" || t.signal === "sell")
    .slice(0, 5);

  return (
    <div className="space-y-20">
      {/* Hero */}
      <section className="fade-up pt-6 md:pt-10">
        <div className="max-w-2xl">
          <div className="mb-4 inline-flex items-center gap-2 rounded-full border bg-muted px-3 py-1 text-[11px] font-medium text-muted-foreground">
            <span className="size-1.5 rounded-full bg-emerald-500" aria-hidden />
            {briefed.length} tickers analyzed today
          </div>
          <h1 className="text-3xl font-semibold tracking-tight text-foreground md:text-4xl lg:text-5xl">
            AI reads the tape.{" "}
            <span className="text-muted-foreground">You make the call.</span>
          </h1>
          <p className="mt-4 max-w-lg text-base leading-relaxed text-muted-foreground">
            Four specialist agents debate every ticker. One synthesizer turns the noise into a
            briefing with conviction scores, entry levels, and stop-losses — updated daily.
          </p>
          <div className="mt-8 flex flex-wrap items-center gap-3">
            <Link
              href="/dashboard"
              className="inline-flex h-10 items-center gap-2 rounded-lg bg-foreground px-5 text-sm font-medium text-background transition-colors hover:bg-foreground/90"
            >
              Browse all tickers
              <ArrowRight className="size-4" />
            </Link>
            {topBuys[0] && (
              <Link
                href={`/${topBuys[0].symbol}`}
                className="inline-flex h-10 items-center gap-2 rounded-lg border bg-background px-5 text-sm font-medium text-foreground transition-colors hover:bg-muted"
              >
                Top conviction: {topBuys[0].symbol}
              </Link>
            )}
          </div>
        </div>
      </section>

      {/* How it works */}
      <section aria-labelledby="how-it-works">
        <h2
          id="how-it-works"
          className="mb-8 text-xs font-semibold uppercase tracking-widest text-muted-foreground"
        >
          How it works
        </h2>
        <div className="grid gap-6 sm:grid-cols-3">
          {AGENTS.map((a) => (
            <div key={a.step} className="rounded-xl border bg-card p-6">
              <div className="num mb-3 text-[11px] font-medium text-muted-foreground/60">
                {a.step}
              </div>
              <div className="mb-2 text-sm font-semibold text-foreground">{a.name}</div>
              <p className="text-xs leading-relaxed text-muted-foreground">{a.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Conviction leaders */}
      {(topBuys.length > 0 || topSells.length > 0) && (
        <section aria-labelledby="leaders">
          <div className="mb-6 flex items-center justify-between">
            <h2
              id="leaders"
              className="text-xs font-semibold uppercase tracking-widest text-muted-foreground"
            >
              Today&apos;s conviction leaders
            </h2>
            <Link
              href="/dashboard"
              className="text-xs text-muted-foreground underline-offset-4 hover:text-foreground hover:underline"
            >
              Browse all →
            </Link>
          </div>
          <div className="grid gap-6 md:grid-cols-2">
            {topBuys.length > 0 && (
              <LeaderColumn
                title="Bullish"
                icon={<TrendingUp className="size-3.5 text-emerald-600" />}
                tickers={topBuys}
              />
            )}
            {topSells.length > 0 && (
              <LeaderColumn
                title="Bearish"
                icon={<TrendingDown className="size-3.5 text-rose-600" />}
                tickers={topSells}
              />
            )}
          </div>
        </section>
      )}
    </div>
  );
}

function LeaderColumn({
  title,
  icon,
  tickers,
}: {
  title: string;
  icon: React.ReactNode;
  tickers: TickerSummary[];
}) {
  return (
    <div className="rounded-xl border bg-card p-5">
      <div className="mb-4 flex items-center gap-1.5 text-[11px] font-semibold text-muted-foreground">
        {icon}
        {title}
      </div>
      <div className="space-y-1">
        {tickers.map((t) => (
          <LeaderRow key={t.symbol} t={t} />
        ))}
      </div>
    </div>
  );
}

function LeaderRow({ t }: { t: TickerSummary }) {
  const up = (t.priceChangePct ?? 0) >= 0;
  return (
    <Link
      href={`/${t.symbol}`}
      className="group flex items-center gap-3 rounded-lg px-3 py-2.5 transition-colors hover:bg-muted"
    >
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className="num text-sm font-semibold text-foreground">{t.symbol}</span>
          <span className="truncate text-[11px] text-muted-foreground">{t.name}</span>
        </div>
      </div>
      <div className="flex shrink-0 items-center gap-3">
        {t.priceChangePct != null && (
          <span
            className={cn(
              "num text-xs font-medium",
              up ? "text-emerald-600" : "text-rose-600",
            )}
          >
            {up ? "+" : ""}
            {fmtSignedPercent(t.priceChangePct)}
          </span>
        )}
        {t.signal && <SignalBadge signal={t.signal} size="sm" />}
        {t.conviction != null && (
          <span className="num text-[11px] text-muted-foreground">
            {t.conviction >= 0 ? "+" : ""}
            {t.conviction.toFixed(2)}
          </span>
        )}
      </div>
    </Link>
  );
}
