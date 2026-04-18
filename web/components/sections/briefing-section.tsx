import { ShieldAlert, Sparkles } from "lucide-react";
import { SectionCard } from "./section-card";
import { SignalBadge } from "@/components/signal-badge";
import { ConvictionMeter } from "@/components/conviction-meter";
import type { Briefing, Signal } from "@/lib/types";

export function BriefingSection({ data }: { data: Briefing }) {
  return (
    <SectionCard
      id="briefing"
      title="Executive briefing"
      description={`Synthesized from all four layers · ${data.date}`}
      action={<SignalBadge signal={data.overall_signal} size="lg" />}
    >
      <div className="grid gap-6 lg:grid-cols-[1fr_320px]">
        <div className="space-y-5">
          <p className="text-[15px] leading-relaxed">{data.executive_summary}</p>

          <div className="grid gap-3 sm:grid-cols-2">
            <CasePanel title="Bull case" text={data.bull_case} tone="bull" />
            <CasePanel title="Bear case" text={data.bear_case} tone="bear" />
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <div className="rounded-lg border border-border/50 bg-muted/20 p-4">
              <h4 className="mb-2 flex items-center gap-2 text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
                <Sparkles className="size-3.5" /> Catalysts
              </h4>
              {data.catalysts_upcoming.length ? (
                <ul className="space-y-1 text-sm">
                  {data.catalysts_upcoming.map((c, i) => (
                    <li key={i}>· {c}</li>
                  ))}
                </ul>
              ) : (
                <p className="text-sm text-muted-foreground">None flagged</p>
              )}
            </div>
            <div className="rounded-lg border border-border/50 bg-muted/20 p-4">
              <h4 className="mb-2 flex items-center gap-2 text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
                <ShieldAlert className="size-3.5" /> Key uncertainties
              </h4>
              {data.key_uncertainties.length ? (
                <ul className="space-y-1 text-sm">
                  {data.key_uncertainties.map((c, i) => (
                    <li key={i}>· {c}</li>
                  ))}
                </ul>
              ) : (
                <p className="text-sm text-muted-foreground">None flagged</p>
              )}
            </div>
          </div>

          <div className="rounded-lg border border-border/50 bg-muted/20 p-4">
            <h4 className="mb-3 text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
              Risk assessment
            </h4>
            <dl className="grid gap-3 sm:grid-cols-2 text-sm">
              <div>
                <dt className="text-muted-foreground">Position size</dt>
                <dd className="mt-0.5">{data.risk_assessment.position_size_suggestion}</dd>
              </div>
              {data.risk_assessment.risk_reward_ratio && (
                <div>
                  <dt className="text-muted-foreground">Risk / reward</dt>
                  <dd className="mt-0.5 num">{data.risk_assessment.risk_reward_ratio}</dd>
                </div>
              )}
              <div className="sm:col-span-2">
                <dt className="text-muted-foreground">Max drawdown scenario</dt>
                <dd className="mt-0.5">{data.risk_assessment.max_drawdown_scenario}</dd>
              </div>
              {data.risk_assessment.correlation_notes.length > 0 && (
                <div className="sm:col-span-2">
                  <dt className="text-muted-foreground">Correlation notes</dt>
                  <dd className="mt-0.5">
                    <ul className="space-y-0.5">
                      {data.risk_assessment.correlation_notes.map((n, i) => (
                        <li key={i}>· {n}</li>
                      ))}
                    </ul>
                  </dd>
                </div>
              )}
            </dl>
          </div>
        </div>

        <aside className="space-y-5">
          <div className="rounded-xl border border-border/50 bg-muted/20 p-5">
            <h4 className="mb-4 text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
              Conviction
            </h4>
            <ConvictionMeter
              score={data.conviction.score}
              convergence={data.conviction.signal_convergence}
            />
            <p className="mt-4 text-xs leading-relaxed text-muted-foreground">
              {data.conviction.explanation}
            </p>
          </div>

          <div className="rounded-xl border border-border/50 bg-muted/20 p-5">
            <h4 className="mb-3 text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
              Agent signals
            </h4>
            <ul className="space-y-2">
              {Object.entries(data.agent_signal_breakdown).map(([k, v]) => (
                <li key={k} className="flex items-center justify-between text-sm">
                  <span className="capitalize text-muted-foreground">{k}</span>
                  <SignalBadge signal={v as Signal} size="sm" />
                </li>
              ))}
            </ul>
          </div>
        </aside>
      </div>
    </SectionCard>
  );
}

function CasePanel({
  title,
  text,
  tone,
}: {
  title: string;
  text: string;
  tone: "bull" | "bear";
}) {
  const tint =
    tone === "bull"
      ? "border-emerald-500/30 bg-emerald-500/5"
      : "border-rose-500/30 bg-rose-500/5";
  const color = tone === "bull" ? "text-emerald-400" : "text-rose-400";
  return (
    <div className={`rounded-lg border p-4 ${tint}`}>
      <h5 className={`mb-1.5 text-[11px] font-semibold uppercase tracking-wider ${color}`}>
        {title}
      </h5>
      <p className="text-sm leading-relaxed">{text}</p>
    </div>
  );
}
