import { TrendingDown, TrendingUp } from "lucide-react";
import { SectionCard } from "@/components/shared/section-card";
import { cn } from "@/lib/utils";
import type { DebateArgument, DebateResult } from "@/lib/types";

export function DebateSection({ data }: { data: DebateResult }) {
  return (
    <SectionCard
      id="debate"
      tier="argument"
      layer="Layer 3 · Adversarial debate"
      title="The debate"
      description={`${data.rounds.length} adversarial rounds`}
    >
      <div className="grid gap-x-8 gap-y-6 md:grid-cols-2">
        <CaseSummary side="bull" text={data.bull_case_summary} />
        <CaseSummary side="bear" text={data.bear_case_summary} />
      </div>

      <div className="relative mt-10 space-y-8 border-l pl-6">
        {data.rounds.map((r) => (
          <div key={r.round_number} className="relative">
            <span
              className="absolute -left-[25px] top-1.5 size-2 rounded-full bg-ink ring-4 ring-background"
              aria-hidden
            />
            <h3 className="eyebrow mb-3">
              Round <span className="num">{r.round_number}</span>
            </h3>
            <div className="grid gap-x-8 gap-y-6 md:grid-cols-2">
              <Argument side="bull" arg={r.bull_argument} />
              <Argument side="bear" arg={r.bear_argument} />
            </div>
          </div>
        ))}
      </div>

      <div className="mt-10 grid gap-6 md:grid-cols-3">
        <ListBox title="Agreements" items={data.key_points_of_agreement} />
        <ListBox title="Disagreements" items={data.key_points_of_disagreement} />
        <ListBox title="Unresolved" items={data.unresolved_uncertainties} />
      </div>
    </SectionCard>
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
      {arg.key_points.length > 0 && (
        <ul className="mt-3 space-y-1.5 border-t pt-3">
          {arg.key_points.map((p, i) => (
            <li key={i} className="flex gap-2">
              <span className="text-graphite" aria-hidden>
                ›
              </span>
              <span className="prose-claim max-w-[68ch] text-sm">{p}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function ListBox({ title, items }: { title: string; items: string[] }) {
  return (
    <div>
      <h3 className="eyebrow mb-2 border-b pb-2">{title}</h3>
      {items.length > 0 ? (
        <ul className="space-y-2">
          {items.map((t, idx) => (
            <li key={idx} className="flex gap-2">
              <span className="text-graphite" aria-hidden>
                —
              </span>
              <span className="prose-claim max-w-[68ch] text-sm">{t}</span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-sm text-graphite">None</p>
      )}
    </div>
  );
}
