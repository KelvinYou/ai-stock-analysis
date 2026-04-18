import { ShieldAlert, Sparkles, Target, Users } from "lucide-react";
import { SectionCard } from "@/components/shared/section-card";
import { fmtCurrency } from "@/lib/format";
import { SignalBadge } from "./signal-badge";
import { ConvictionMeter } from "./conviction-meter";
import type { ActionPlan, Briefing, Signal } from "@/lib/types";

export function BriefingSection({ data, currency }: { data: Briefing; currency: string }) {
  return (
    <SectionCard
      id="briefing"
      chapter="02"
      title="The Brief"
      description={`Synthesis of all four layers · ${data.date}`}
      action={<SignalBadge signal={data.overall_signal} size="lg" />}
      flush
    >
      <div className="grid gap-0 lg:grid-cols-[1fr_340px]">
        <div className="space-y-8 p-6 md:p-8 lg:border-r hairline">
          <div>
            <div className="mb-3 text-[10px] uppercase tracking-[0.26em] text-primary">
              Lead
            </div>
            <p className="display text-lg leading-relaxed text-foreground md:text-xl">
              {data.executive_summary}
            </p>
          </div>

          {data.action_plan && (
            <ActionPlanPanel plan={data.action_plan} currency={currency} />
          )}

          <div className="grid gap-4 md:grid-cols-2">
            <CasePanel title="Bull case" text={data.bull_case} tone="bull" />
            <CasePanel title="Bear case" text={data.bear_case} tone="bear" />
          </div>

          <div className="grid gap-5 md:grid-cols-2">
            <Pullout
              icon={<Sparkles className="size-3.5" />}
              title="Catalysts ahead"
              items={data.catalysts_upcoming}
              accent="text-primary"
            />
            <Pullout
              icon={<ShieldAlert className="size-3.5" />}
              title="Key uncertainties"
              items={data.key_uncertainties}
              accent="text-amber-300"
            />
          </div>

          <div>
            <div className="mb-3 text-[10px] uppercase tracking-[0.26em] text-muted-foreground/80">
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
                          <span className="text-primary/70">—</span>
                          {n}
                        </li>
                      ))}
                    </ul>
                  }
                />
              )}
            </dl>
          </div>
        </div>

        <aside className="space-y-6 bg-muted/10 p-6 md:p-8">
          <div>
            <div className="mb-4 text-[10px] uppercase tracking-[0.26em] text-muted-foreground/80">
              Conviction meter
            </div>
            <ConvictionMeter
              score={data.conviction.score}
              convergence={data.conviction.signal_convergence}
            />
            <p className="mt-5 border-t hairline pt-4 text-xs leading-relaxed text-muted-foreground">
              {data.conviction.explanation}
            </p>
          </div>

          <div className="border-t hairline pt-6">
            <div className="mb-3 flex items-center gap-2 text-[10px] uppercase tracking-[0.26em] text-muted-foreground/80">
              <Users className="size-3.5" />
              <span>Agent signals</span>
            </div>
            <ul className="space-y-2">
              {Object.entries(data.agent_signal_breakdown).map(([k, v]) => (
                <li key={k} className="flex items-center justify-between text-sm">
                  <span className="text-muted-foreground capitalize">{k}</span>
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
      <dt className="text-[10px] uppercase tracking-[0.22em] text-muted-foreground/80">{label}</dt>
      <dd className="mt-1.5 leading-relaxed text-foreground/95">{value}</dd>
    </div>
  );
}

function Pullout({
  icon,
  title,
  items,
  accent,
}: {
  icon: React.ReactNode;
  title: string;
  items: string[];
  accent: string;
}) {
  return (
    <div className="border-l-2 border-border/40 pl-4">
      <h4
        className={`mb-2.5 flex items-center gap-2 text-[10px] uppercase tracking-[0.22em] ${accent}`}
      >
        {icon}
        {title}
      </h4>
      {items.length ? (
        <ul className="space-y-1.5 text-sm leading-relaxed">
          {items.map((c, i) => (
            <li key={i} className="flex gap-2">
              <span className="num text-muted-foreground/60">
                {String(i + 1).padStart(2, "0")}
              </span>
              <span>{c}</span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-sm italic text-muted-foreground/70">None flagged</p>
      )}
    </div>
  );
}

function ActionPlanPanel({
  plan,
  currency,
}: {
  plan: ActionPlan;
  currency: string;
}) {
  const hasLevels =
    plan.entry_limit !== null ||
    plan.stop_loss !== null ||
    plan.take_profit_1 !== null;

  if (!hasLevels) {
    return (
      <div className="rounded-sm border hairline bg-muted/10 p-5">
        <div className="mb-2 flex items-center gap-2 text-[10px] uppercase tracking-[0.26em] text-muted-foreground/80">
          <Target className="size-3.5" />
          Action plan
        </div>
        <p className="text-sm leading-relaxed text-muted-foreground">
          {plan.note ?? "Signal too mixed for precise levels — wait for a clearer setup."}
        </p>
      </div>
    );
  }

  return (
    <div className="rounded-sm border hairline bg-background/40 p-5">
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-2 text-[10px] uppercase tracking-[0.26em] text-primary">
          <Target className="size-3.5" />
          Action plan
        </div>
        <span className="text-[10px] uppercase tracking-[0.22em] text-muted-foreground/70">
          {plan.horizon}
        </span>
      </div>

      <div className="grid gap-4 sm:grid-cols-3">
        <LevelTile
          label={plan.entry_limit !== null ? "Entry limit" : "No new entry"}
          price={plan.entry_limit}
          rationale={plan.entry_rationale}
          currency={currency}
          tone="entry"
        />
        <LevelTile
          label="Stop loss"
          price={plan.stop_loss}
          rationale={plan.stop_rationale}
          currency={currency}
          tone="stop"
        />
        <LevelTile
          label="Take profit"
          price={plan.take_profit_1}
          secondary={plan.take_profit_2}
          rationale={plan.target_rationale}
          currency={currency}
          tone="target"
        />
      </div>

      <p className="mt-4 border-t hairline pt-3 text-[11px] leading-relaxed text-muted-foreground/80">
        Guidance only — derived from technicals, not financial advice. Size positions per
        the risk block below and adjust to your own plan.
      </p>
    </div>
  );
}

function LevelTile({
  label,
  price,
  secondary,
  rationale,
  currency,
  tone,
}: {
  label: string;
  price: number | null;
  secondary?: number | null;
  rationale: string | null;
  currency: string;
  tone: "entry" | "stop" | "target";
}) {
  const accent =
    tone === "entry"
      ? "text-primary"
      : tone === "stop"
        ? "text-rose-300"
        : "text-emerald-300";

  return (
    <div className="border-l-2 border-border/40 pl-3">
      <div
        className={`mb-1.5 text-[10px] uppercase tracking-[0.22em] ${accent}`}
      >
        {label}
      </div>
      <div className="num text-lg font-semibold text-foreground">
        {price !== null ? fmtCurrency(price, currency) : "—"}
        {secondary != null && (
          <span className="ml-2 text-xs font-normal text-muted-foreground/80">
            → {fmtCurrency(secondary, currency)}
          </span>
        )}
      </div>
      {rationale && (
        <p className="mt-1.5 text-xs leading-relaxed text-muted-foreground">
          {rationale}
        </p>
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
  const accent =
    tone === "bull"
      ? "before:bg-emerald-400 text-emerald-300"
      : "before:bg-rose-400 text-rose-300";
  return (
    <article
      className={`relative overflow-hidden rounded-sm border hairline bg-background/40 p-5 before:absolute before:left-0 before:top-0 before:h-full before:w-[3px] ${accent.split(" ")[0]}`}
    >
      <h5
        className={`mb-2 text-[10px] font-semibold uppercase tracking-[0.26em] ${accent.split(" ")[1]}`}
      >
        {title}
      </h5>
      <p className="text-sm leading-relaxed text-foreground/95">{text}</p>
    </article>
  );
}
