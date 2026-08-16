import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { PipelineDiagram } from "@/components/about/pipeline-diagram";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { loadPipeline } from "@/lib/pipeline";

export const metadata = {
  title: "How it works · Desk",
};

export const revalidate = 60;

/**
 * The one page with room to breathe. Everywhere else the type is set for
 * density; here the hero runs Archivo wide and large, because this is the page
 * that has to say what the machine is before you trust a number it produced.
 */
export default async function AboutPage() {
  const pipeline = await loadPipeline();

  return (
    <div className="space-y-16">
      <section className="fade-up pt-6 md:pt-10">
        <div className="max-w-3xl">
          <p className="eyebrow">Four layers, one briefing</p>
          <h1 className="mt-3 text-4xl font-semibold leading-[0.98] tracking-[-0.03em] text-ink [font-stretch:125%] md:text-6xl lg:text-7xl">
            AI reads the tape.
            <br />
            <span className="text-graphite">You make the call.</span>
          </h1>
          <p className="prose-claim mt-6 max-w-xl">
            Four specialist agents debate every ticker. One synthesizer turns the noise
            into a briefing with conviction scores, entry levels, and stop-losses.
          </p>
          <div className="mt-8">
            {/* The page's one call to action, so it takes the one interactive
                colour. Everything structural on this page stays ink. */}
            <Button asChild variant="default" size="lg">
              <Link href="/">
                Open the screener
                <ArrowRight className="size-4" />
              </Link>
            </Button>
          </div>
        </div>
      </section>

      <section aria-labelledby="how-it-works">
        <h2 id="how-it-works" className="eyebrow mb-2">
          How it works
        </h2>
        <Separator className="mb-6" />
        <ol className="mb-8 grid gap-x-8 gap-y-5 sm:grid-cols-2 lg:grid-cols-4">
          <Layer n="Layer 1" name="Ingestion">
            Prices, financials, filings and news are fetched deterministically. No
            model has spoken yet, so nothing here can be argued with.
          </Layer>
          <Layer n="Layer 2" name="Four desks">
            Fundamentals, Technical, Sentiment and Macro·FX read the same data
            independently and each return a signal with a confidence.
          </Layer>
          <Layer n="Layer 3" name="Debate">
            A bull and a bear argue the four reports over several rounds; a research
            manager then rules on the argument and records what would falsify it.
          </Layer>
          <Layer n="Layer 4" name="Synthesis">
            The briefing is assembled, and a deterministic risk check attaches entry,
            stop and target — but only when the desks converged enough to justify them.
          </Layer>
        </ol>
        {pipeline ? (
          <PipelineDiagram pipeline={pipeline} />
        ) : (
          <p className="rounded-lg border border-dashed p-6 text-sm text-graphite">
            Pipeline description not found — expected{" "}
            <code className="num text-xs">pipeline.json</code> at the repo root.
          </p>
        )}
      </section>

      <section aria-labelledby="reading-the-desk">
        <h2 id="reading-the-desk" className="eyebrow mb-2">
          Reading the screener
        </h2>
        <Separator className="mb-6" />
        <dl className="grid gap-x-8 gap-y-3 text-sm sm:grid-cols-2">
          <Term name="Conv">
            Conviction, −1.00 to +1.00. Magnitude is how hard the synthesizer is
            leaning, sign is the direction.
          </Term>
          <Term name="Cvg">
            Signal convergence. Below 0.50 the four analysts disagreed — the briefing
            is an arbitration, not a consensus, so read the debate.
          </Term>
          <Term name="→Entry">
            Distance from last close to the suggested entry limit. Negative means the
            price still has to fall; ≥ 0 means it is already at or below entry.
          </Term>
          <Term name="Age">
            Days since the briefing was generated. Price data refreshes daily via
            <code className="num mx-1 text-micro">stock-fetch</code>; briefings
            only when you run the pipeline.
          </Term>
        </dl>
      </section>
    </div>
  );
}

function Layer({
  n,
  name,
  children,
}: {
  n: string;
  name: string;
  children: React.ReactNode;
}) {
  return (
    <li className="border-t-2 border-ink pt-3">
      <p className="num text-micro text-graphite">{n}</p>
      <h3 className="mt-1 text-base font-semibold tracking-[-0.02em] text-ink [font-stretch:125%]">
        {name}
      </h3>
      <p className="prose-claim mt-1.5 text-xs">{children}</p>
    </li>
  );
}

function Term({ name, children }: { name: string; children: React.ReactNode }) {
  return (
    <div className="border-t pt-3">
      <dt className="num text-xs font-semibold text-ink">{name}</dt>
      <dd className="mt-1 text-xs leading-relaxed text-graphite">{children}</dd>
    </div>
  );
}
