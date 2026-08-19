import { ChevronDown, TrendingDown, TrendingUp } from "lucide-react";
import { SectionCard } from "@/components/shared/section-card";
import { cn } from "@/lib/utils";
import { signalLabel } from "@/lib/format";
import type { DebateArgument, DebateResult, ResearchVerdict } from "@/lib/types";

export function DebateSection({
  data,
  verdict,
}: {
  data: DebateResult;
  verdict?: ResearchVerdict | null;
}) {
  return (
    <SectionCard
      id="debate"
      tier="argument"
      layer="Layer 3 · Adversarial debate"
      title="The debate"
      description={`${data.rounds.length} adversarial rounds · structured argument board`}
    >
      <div className="space-y-8">
        <div className="grid gap-x-8 gap-y-6 md:grid-cols-2">
          <CaseSummary side="bull" text={data.bull_case_summary} />
          <CaseSummary side="bear" text={data.bear_case_summary} />
        </div>

        <DebateBoard data={data} />

        {verdict && <VerdictBlock verdict={verdict} />}

        {data.rounds.length > 0 && <RoundTimeline rounds={data.rounds} />}
      </div>
    </SectionCard>
  );
}

function DebateBoard({ data }: { data: DebateResult }) {
  const total =
    data.key_points_of_agreement.length +
    data.key_points_of_disagreement.length +
    data.unresolved_uncertainties.length;

  return (
    <section aria-labelledby="debate-board-title">
      <div className="flex flex-wrap items-baseline justify-between gap-2 border-t pt-5">
        <div>
          <h3 id="debate-board-title" className="text-sm font-semibold text-ink">
            What survived the debate
          </h3>
          <p className="mt-1 text-micro text-graphite">
            Agreement, disagreement, and unknowns stay separate
          </p>
        </div>
        <span className="num text-micro text-graphite">{total} structured points</span>
      </div>

      <div className="mt-5 grid gap-6 md:grid-cols-3">
        <ListBox
          title="Agreements"
          description="Both sides accept"
          items={data.key_points_of_agreement}
          tone="up"
        />
        <ListBox
          title="Disagreements"
          description="The argument turns here"
          items={data.key_points_of_disagreement}
          tone="neutral"
        />
        <ListBox
          title="Unresolved"
          description="Evidence still missing"
          items={data.unresolved_uncertainties}
          tone="halt"
        />
      </div>
    </section>
  );
}

function VerdictBlock({ verdict }: { verdict: ResearchVerdict }) {
  const winningSide =
    verdict.winning_side === "neither"
      ? "No side declared"
      : `${verdict.winning_side === "bull" ? "Bull" : "Bear"} carried the argument`;
  const conditions = verdict.invalidation_conditions.length
    ? verdict.invalidation_conditions
    : verdict.evidence_gaps;

  return (
    <section className="border-y py-5" aria-labelledby="research-verdict-title">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <div>
          <h3 id="research-verdict-title" className="text-sm font-semibold text-ink">
            Research manager verdict
          </h3>
          <p className="mt-1 text-micro text-graphite">
            {winningSide} · {signalLabel(verdict.judged_view)} view · {verdict.confidence} confidence
          </p>
        </div>
      </div>

      <p className="prose-claim mt-4 max-w-[72ch]">{verdict.thesis}</p>

      <div className="mt-5 grid gap-6 md:grid-cols-3">
        <VerdictColumn title="Strongest counterexample" items={[verdict.strongest_counterexample]} />
        <VerdictColumn title="Invalidation conditions" items={conditions} />
        <VerdictColumn title="Decisive factors" items={verdict.decisive_factors} />
      </div>
    </section>
  );
}

function VerdictColumn({ title, items }: { title: string; items: string[] }) {
  return (
    <div>
      <h4 className="eyebrow mb-2 border-b pb-2">{title}</h4>
      {items.length > 0 ? (
        <ul className="space-y-2">
          {items.map((item, index) => (
            <li key={index} className="flex gap-2">
              <span className="text-graphite" aria-hidden>
                —
              </span>
              <span className="prose-claim text-sm">{item}</span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-sm text-graphite">None reported</p>
      )}
    </div>
  );
}

function RoundTimeline({ rounds }: { rounds: DebateResult["rounds"] }) {
  return (
    <section aria-labelledby="rounds-title">
      <div className="flex flex-wrap items-baseline justify-between gap-2 border-t pt-5">
        <div>
          <h3 id="rounds-title" className="text-sm font-semibold text-ink">
            Round-by-round case building
          </h3>
          <p className="mt-1 text-micro text-graphite">
            Open a round for the full arguments and rebuttals
          </p>
        </div>
        <span className="eyebrow">Timeline</span>
      </div>

      <div className="relative mt-5 space-y-3 border-l pl-6">
        {rounds.map((round) => (
          <details key={round.round_number} className="group relative border-b pb-3 last:border-b-0">
            <span
              className="absolute -left-[25px] top-1.5 size-2 rounded-full bg-ink ring-4 ring-background"
              aria-hidden
            />
            <summary className="flex cursor-pointer list-none items-center justify-between gap-3 py-1">
              <span className="eyebrow">
                Round <span className="num">{round.round_number}</span>
              </span>
              <ChevronDown
                className="size-3.5 text-graphite transition-transform group-open:rotate-180"
                aria-hidden
              />
            </summary>
            <div className="mt-4 grid gap-x-8 gap-y-6 md:grid-cols-2">
              <Argument side="bull" arg={round.bull_argument} />
              <Argument side="bear" arg={round.bear_argument} />
            </div>
          </details>
        ))}
      </div>
    </section>
  );
}

/**
 * Two columns of one argument — a left rule and the barest wash, not two
 * boxed-in tinted cards. The side is named in the heading and drawn by the
 * trend icon; the hue on the rule and label is the third, redundant cue. Body
 * prose stays in default ink so an argument is never tinted into being read as
 * weaker than the one beside it.
 */
const SIDE = {
  bull: {
    label: "Bull case",
    short: "Bull",
    Icon: TrendingUp,
    rule: "border-bull bg-bull/[0.05]",
    text: "text-bull",
  },
  bear: {
    label: "Bear case",
    short: "Bear",
    Icon: TrendingDown,
    rule: "border-bear bg-bear/[0.05]",
    text: "text-bear",
  },
} as const;

type Side = keyof typeof SIDE;

function CaseSummary({ side, text }: { side: Side; text: string }) {
  const { label, Icon, rule, text: tone } = SIDE[side];
  return (
    <article className={cn("border-l-2 py-2 pl-4 pr-3", rule)}>
      <h3 className={cn("eyebrow mb-1.5 flex items-center gap-1.5", tone)}>
        <Icon className="size-3.5" aria-hidden />
        {label}
      </h3>
      <p className="prose-claim max-w-[68ch]">{text}</p>
    </article>
  );
}

function Argument({ side, arg }: { side: Side; arg: DebateArgument }) {
  const { short, rule, text: tone } = SIDE[side];
  return (
    <div className={cn("border-l-2 py-2 pl-4 pr-3", rule)}>
      <h4 className={cn("eyebrow mb-1.5", tone)}>{short}</h4>
      <p className="prose-claim max-w-[68ch]">{arg.argument}</p>
      {arg.rebuttal_to_previous && (
        <p className="prose-claim mt-3 border-t pt-3 text-sm">
          <span className="eyebrow mr-2">Rebuttal</span>
          {arg.rebuttal_to_previous}
        </p>
      )}
      {arg.key_points.length > 0 && (
        <ul className="mt-3 space-y-1.5 border-t pt-3">
          {arg.key_points.map((point, index) => (
            <li key={index} className="flex gap-2">
              <span className="text-graphite" aria-hidden>
                ›
              </span>
              <span className="prose-claim max-w-[68ch] text-sm">{point}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function ListBox({
  title,
  description,
  items,
  tone,
}: {
  title: string;
  description: string;
  items: string[];
  tone: "up" | "neutral" | "halt";
}) {
  const toneClass =
    tone === "up" ? "text-bull" : tone === "halt" ? "text-halt" : "text-ink";
  return (
    <div>
      <div className="flex items-baseline justify-between gap-2 border-b pb-2">
        <h3 className={cn("eyebrow", toneClass)}>{title}</h3>
        <span className="num text-micro text-graphite">{items.length}</span>
      </div>
      <p className="mt-1.5 text-micro text-graphite">{description}</p>
      {items.length > 0 ? (
        <ul className="mt-3 space-y-2">
          {items.map((text, index) => (
            <li key={index} className="flex gap-2">
              <span className={cn("mt-1 text-xs", toneClass)} aria-hidden>
                {tone === "up" ? "▲" : tone === "halt" ? "!" : "—"}
              </span>
              <span className="prose-claim text-sm">{text}</span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="mt-3 text-sm text-graphite">None reported</p>
      )}
    </div>
  );
}
