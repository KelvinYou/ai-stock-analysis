import { ChevronDown, ShieldAlert, Sparkles, TrendingDown, TrendingUp, Users } from "lucide-react";
import { SectionCard } from "@/components/shared/section-card";
import { SignalBadge } from "./signal-badge";
import { cn } from "@/lib/utils";
import type { Briefing, Signal } from "@/lib/types";

export function BriefingSection({ data }: { data: Briefing; currency?: string }) {
  const convergencePct = Math.round(data.conviction.signal_convergence * 100);
  const score = data.conviction.score;
  const scoreSign = score >= 0 ? "+" : "";
  const scoreStr = `${scoreSign}${score.toFixed(2)}`;
  // The signed number carries the direction on its own; hue rides along with it.
  // Zero is a real answer here, not a rounding artefact, so it stays neutral.
  const convictionText =
    score > 0 ? "text-bull" : score < 0 ? "text-bear" : "text-graphite";
  const convictionFill = score > 0 ? "bg-bull" : score < 0 ? "bg-bear" : "bg-graphite";

  return (
    <SectionCard
      id="briefing"
      tier="argument"
      layer="Layer 4 · Synthesis"
      title="The brief"
      description={`Synthesis of all four layers · ${data.date}`}
      action={<SignalBadge signal={data.overall_signal} size="lg" />}
    >
      <div className="space-y-8">
        <div>
          <h3 className="eyebrow mb-2">Summary</h3>
          <p className="prose-claim max-w-[68ch] text-base">{data.executive_summary}</p>
        </div>

        <details className="group rounded-lg border bg-card">
          <summary className="flex cursor-pointer list-none items-center justify-between gap-3 px-4 py-3 transition-colors hover:bg-muted/40">
            <h3 className="flex items-center gap-2 text-sm font-medium text-ink">
              <ChevronDown
                className="size-3.5 transition-transform group-open:rotate-180"
                aria-hidden
              />
              Why this conviction?
            </h3>
            <span className="num text-xs text-graphite">
              score <span className={convictionText}>{scoreStr}</span> · {convergencePct}%
              convergence
            </span>
          </summary>
          <div className="space-y-5 border-t px-4 py-4 md:px-5">
            <div>
              <div className="mb-1.5 flex items-center justify-between gap-3">
                <h4 className="eyebrow">Signal convergence</h4>
                <span className="num text-micro text-ink">{convergencePct}%</span>
              </div>
              <div
                className="h-1 w-full overflow-hidden rounded-full bg-muted"
                role="progressbar"
                aria-valuenow={convergencePct}
                aria-valuemin={0}
                aria-valuemax={100}
                aria-label={`Signal convergence ${convergencePct} percent`}
              >
                <div
                  className={cn("h-full rounded-full", convictionFill)}
                  style={{ width: `${convergencePct}%` }}
                />
              </div>
            </div>

            <div>
              <h4 className="eyebrow mb-2.5 flex items-center gap-2">
                <Users className="size-3.5" aria-hidden />
                Agent breakdown
              </h4>
              <ul className="grid gap-2 sm:grid-cols-2">
                {Object.entries(data.agent_signal_breakdown).map(([k, v]) => (
                  <li
                    key={k}
                    className="flex items-center justify-between gap-3 rounded border px-3 py-2"
                  >
                    <span className="text-xs capitalize text-graphite">{k}</span>
                    <SignalBadge signal={v as Signal} size="sm" />
                  </li>
                ))}
              </ul>
            </div>

            <p className="prose-claim max-w-[68ch] text-xs">{data.conviction.explanation}</p>
          </div>
        </details>

        <div className="grid gap-x-8 gap-y-6 md:grid-cols-2">
          <CasePanel side="bull" text={data.bull_case} />
          <CasePanel side="bear" text={data.bear_case} />
        </div>

        <div className="grid gap-6 md:grid-cols-2">
          <Pullout
            icon={<Sparkles className="size-3.5" aria-hidden />}
            title="Catalysts ahead"
            items={data.catalysts_upcoming}
          />
          <Pullout
            icon={<ShieldAlert className="size-3.5" aria-hidden />}
            title="Key uncertainties"
            items={data.key_uncertainties}
          />
        </div>

        <div>
          <h3 className="eyebrow mb-3 border-b pb-2">Risk assessment</h3>
          <dl className="grid gap-x-8 gap-y-4 md:grid-cols-2">
            {data.risk_assessment.risk_reward_ratio && (
              <DlRow
                label="Risk / reward"
                value={
                  <span className="num text-sm text-ink">
                    {data.risk_assessment.risk_reward_ratio}
                  </span>
                }
              />
            )}
            <DlRow
              label="Max drawdown scenario"
              value={
                <p className="prose-claim max-w-[68ch] text-sm">
                  {data.risk_assessment.max_drawdown_scenario}
                </p>
              }
              span
            />
            {data.risk_assessment.correlation_notes.length > 0 && (
              <DlRow
                label="Market context"
                span
                value={
                  <ul className="space-y-1.5">
                    {data.risk_assessment.correlation_notes.map((n, i) => (
                      <li key={i} className="flex gap-2">
                        <span className="text-graphite" aria-hidden>
                          —
                        </span>
                        <span className="prose-claim max-w-[68ch] text-sm">{n}</span>
                      </li>
                    ))}
                  </ul>
                }
              />
            )}
          </dl>
        </div>
      </div>
    </SectionCard>
  );
}

function DlRow({
  label,
  value,
  span,
}: {
  label: string;
  value: React.ReactNode;
  span?: boolean;
}) {
  return (
    <div className={span ? "md:col-span-2" : undefined}>
      <dt className="eyebrow">{label}</dt>
      <dd className="mt-1">{value}</dd>
    </div>
  );
}

function Pullout({
  icon,
  title,
  items,
}: {
  icon: React.ReactNode;
  title: string;
  items: string[];
}) {
  return (
    <div>
      <h3 className="eyebrow mb-2 flex items-center gap-2">
        {icon}
        {title}
      </h3>
      {items.length ? (
        <ul className="space-y-2">
          {items.map((c, i) => (
            <li key={i} className="flex gap-2.5">
              <span
                className="mt-2 inline-block size-1 shrink-0 rounded-full bg-graphite"
                aria-hidden
              />
              <span className="prose-claim max-w-[68ch] text-sm">{c}</span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-sm text-graphite">None flagged</p>
      )}
    </div>
  );
}

/**
 * Bull and bear read as two columns of one argument. The heading names the
 * side, the icon shows the direction, and the hue on the rule and label is the
 * third, redundant cue. A left rule and a 5%-opacity wash, not a boxed tinted
 * card — and the prose itself stays default ink, so neither case is tinted into
 * looking like the weaker one.
 */
const SIDE = {
  bull: {
    label: "Bull case",
    Icon: TrendingUp,
    rule: "border-bull bg-bull/[0.05]",
    text: "text-bull",
  },
  bear: {
    label: "Bear case",
    Icon: TrendingDown,
    rule: "border-bear bg-bear/[0.05]",
    text: "text-bear",
  },
} as const;

function CasePanel({ side, text }: { side: keyof typeof SIDE; text: string }) {
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
