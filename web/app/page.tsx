import { TickerCard } from "@/components/ticker-card";
import { listTickerSummaries } from "@/lib/data";

export const revalidate = 0;

export default async function HomePage() {
  const tickers = await listTickerSummaries();
  const withBriefing = tickers.filter((t) => t.signal != null).length;

  return (
    <div className="space-y-10">
      <section className="animate-fade-in space-y-3">
        <span className="inline-flex items-center gap-2 rounded-full border border-border/60 bg-muted/40 px-3 py-1 text-xs text-muted-foreground">
          <span className="size-1.5 rounded-full bg-emerald-400" />
          {tickers.length} tickers analyzed · {withBriefing} with full briefing
        </span>
        <h1 className="max-w-3xl text-balance text-4xl font-semibold tracking-tight md:text-5xl">
          Multi-agent stock intelligence,{" "}
          <span className="bg-gradient-to-br from-primary to-fuchsia-400 bg-clip-text text-transparent">
            synthesized for humans.
          </span>
        </h1>
        <p className="max-w-2xl text-balance text-muted-foreground">
          Four specialist agents debate, a synthesizer arbitrates, a risk checker calibrates. Pick a ticker to
          read its briefing.
        </p>
      </section>

      {tickers.length === 0 ? (
        <EmptyState />
      ) : (
        <section className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {tickers.map((t) => (
            <TickerCard key={t.symbol} t={t} />
          ))}
        </section>
      )}
    </div>
  );
}

function EmptyState() {
  return (
    <div className="rounded-xl border border-dashed border-border/60 bg-muted/20 p-10 text-center">
      <p className="text-sm text-muted-foreground">
        No tickers found. Run <code className="rounded bg-muted px-1.5 py-0.5 font-mono">stock-analysis AAPL</code>{" "}
        to generate data under <code className="rounded bg-muted px-1.5 py-0.5 font-mono">data/</code>.
      </p>
    </div>
  );
}
