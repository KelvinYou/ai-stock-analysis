import { ChevronDown, ShieldAlert, Sparkles, Users } from "lucide-react";
import { SectionCard } from "@/components/shared/section-card";
import { SignalBadge } from "./signal-badge";
import type { Briefing, Signal } from "@/lib/types";

export function BriefingSection({ data }: { data: Briefing; currency?: string }) {
  const convergencePct = Math.round(data.conviction.signal_convergence * 100);
  const scoreSign = data.conviction.score >= 0 ? "+" : "";
  const scoreStr = `${scoreSign}${data.conviction.score.toFixed(2)}`;

  return (
    <SectionCard
      id="briefing"
      title="The Brief"
      description={`Synthesis of all four layers · ${data.date}`}
      action={<SignalBadge signal={data.overall_signal} size="lg" />}
    >
      <div className="mx-auto max-w-3xl space-y-7">
        <div>
          <div className="mb-2 text-[11px] font-medium text-muted-foreground">Summary</div>
          <p className="text-base leading-relaxed text-foreground">
            {data.executive_summary}
          </p>
        </div>

        <details className="group rounded-lg border bg-background">
          <summary className="flex cursor-pointer list-none items-center justify-between gap-3 px-4 py-3 text-sm font-medium text-foreground transition-colors hover:bg-muted/40">
            <span className="flex items-center gap-2">
              <ChevronDown className="size-3.5 transition-transform group-open:rotate-180" />
              Why this conviction?
            </span>
            <span className="num text-xs font-normal text-muted-foreground">
              score {scoreStr} · {convergencePct}% convergence
            </span>
          </summary>
          <div className="space-y-5 border-t px-4 py-4 md:px-5">
            <div>
              <div className="mb-1.5 flex items-center justify-between text-[11px] text-muted-foreground">
                <span>Signal convergence</span>
                <span className="num text-foreground">{convergencePct}%</span>
              </div>
              <div className="h-1 w-full overflow-hidden rounded-full bg-muted">
                <div
                  className="h-full rounded-full bg-foreground/80"
                  style={{ width: `${convergencePct}%` }}
                />
              </div>
            </div>

            <div>
              <div className="mb-2.5 flex items-center gap-2 text-[11px] font-medium text-muted-foreground">
                <Users className="size-3.5" />
                Agent breakdown
              </div>
              <ul className="grid gap-2 sm:grid-cols-2">
                {Object.entries(data.agent_signal_breakdown).map(([k, v]) => (
                  <li
                    key={k}
                    className="flex items-center justify-between rounded-md border px-3 py-2 text-sm"
                  >
                    <span className="capitalize text-muted-foreground">{k}</span>
                    <SignalBadge signal={v as Signal} size="sm" />
                  </li>
                ))}
              </ul>
            </div>

            <p className="text-xs leading-relaxed text-muted-foreground">
              {data.conviction.explanation}
            </p>
          </div>
        </details>

        <div className="grid gap-3 md:grid-cols-2">
          <CasePanel title="Bull case" text={data.bull_case} tone="bull" />
          <CasePanel title="Bear case" text={data.bear_case} tone="bear" />
        </div>

        <div className="grid gap-5 md:grid-cols-2">
          <Pullout
            icon={<Sparkles className="size-3.5" />}
            title="Catalysts ahead"
            items={data.catalysts_upcoming}
          />
          <Pullout
            icon={<ShieldAlert className="size-3.5" />}
            title="Key uncertainties"
            items={data.key_uncertainties}
          />
        </div>

        <div>
          <div className="mb-3 text-[11px] font-medium text-muted-foreground">
            Risk assessment
          </div>
          <dl className="grid gap-x-6 gap-y-4 text-sm md:grid-cols-2">
            <DlRow
              label="Position size"
              value={data.risk_assessment.position_size_suggestion}
            />
            {data.risk_assessment.risk_reward_ratio && (
              <DlRow
                label="Risk / reward"
                value={<span className="num">{data.risk_assessment.risk_reward_ratio}</span>}
              />
            )}
            <DlRow
              label="Max drawdown scenario"
              value={data.risk_assessment.max_drawdown_scenario}
              span
            />
            {data.risk_assessment.correlation_notes.length > 0 && (
              <DlRow
                label="Correlation notes"
                span
                value={
                  <ul className="space-y-1">
                    {data.risk_assessment.correlation_notes.map((n, i) => (
                      <li key={i} className="flex gap-2">
                        <span className="text-muted-foreground">—</span>
                        <span>{n}</span>
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
      <dt className="text-[11px] font-medium text-muted-foreground">{label}</dt>
      <dd className="mt-1 leading-relaxed text-foreground">{value}</dd>
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
      <h4 className="mb-2 flex items-center gap-2 text-[11px] font-medium text-muted-foreground">
        {icon}
        {title}
      </h4>
      {items.length ? (
        <ul className="space-y-1.5 text-sm leading-relaxed">
          {items.map((c, i) => (
            <li key={i} className="flex gap-2.5">
              <span className="num mt-1 inline-block size-1 shrink-0 rounded-full bg-foreground/40" />
              <span>{c}</span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-sm text-muted-foreground">None flagged</p>
      )}
    </div>
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
  const toneCls =
    tone === "bull"
      ? "border-emerald-200 bg-emerald-50/50"
      : "border-rose-200 bg-rose-50/50";
  const titleCls = tone === "bull" ? "text-emerald-700" : "text-rose-700";
  return (
    <article className={`rounded-lg border ${toneCls} p-4`}>
      <h5 className={`mb-1.5 text-[11px] font-semibold ${titleCls}`}>{title}</h5>
      <p className="text-sm leading-relaxed text-foreground">{text}</p>
    </article>
  );
}
