import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { PipelineDiagram } from "@/components/about/pipeline-diagram";
import { loadPipeline } from "@/lib/pipeline";

export const metadata = {
  title: "How it works · Desk",
};

export const revalidate = 60;

export default async function AboutPage() {
  const pipeline = await loadPipeline();

  return (
    <div className="space-y-16">
      <section className="fade-up pt-6 md:pt-10">
        <div className="max-w-2xl">
          <h1 className="text-3xl font-semibold tracking-tight text-foreground md:text-4xl lg:text-5xl">
            AI reads the tape.{" "}
            <span className="text-muted-foreground">You make the call.</span>
          </h1>
          <p className="mt-4 max-w-lg text-base leading-relaxed text-muted-foreground">
            Four specialist agents debate every ticker. One synthesizer turns the noise
            into a briefing with conviction scores, entry levels, and stop-losses.
          </p>
          <div className="mt-8">
            <Link
              href="/"
              className="inline-flex h-10 items-center gap-2 rounded-lg bg-foreground px-5 text-sm font-medium text-background transition-colors hover:bg-foreground/90"
            >
              Open the screener
              <ArrowRight className="size-4" />
            </Link>
          </div>
        </div>
      </section>

      <section aria-labelledby="how-it-works">
        <h2
          id="how-it-works"
          className="mb-4 text-xs font-semibold uppercase tracking-widest text-muted-foreground"
        >
          How it works
        </h2>
        {pipeline ? (
          <PipelineDiagram pipeline={pipeline} />
        ) : (
          <p className="rounded-xl border border-dashed p-6 text-sm text-muted-foreground">
            Pipeline description not found — expected{" "}
            <code className="font-mono text-xs">pipeline.json</code> at the repo root.
          </p>
        )}
      </section>

      <section aria-labelledby="reading-the-desk">
        <h2
          id="reading-the-desk"
          className="mb-4 text-xs font-semibold uppercase tracking-widest text-muted-foreground"
        >
          Reading the screener
        </h2>
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
            <code className="mx-1 font-mono text-[11px]">stock-fetch</code>; briefings
            only when you run the pipeline.
          </Term>
        </dl>
      </section>
    </div>
  );
}

function Term({ name, children }: { name: string; children: React.ReactNode }) {
  return (
    <div className="border-t pt-3">
      <dt className="num text-xs font-semibold text-foreground">{name}</dt>
      <dd className="mt-1 text-xs leading-relaxed text-muted-foreground">{children}</dd>
    </div>
  );
}
