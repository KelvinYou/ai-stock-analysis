import { Flag, Target } from "lucide-react";
import { SignalBadge } from "./signal-badge";
import { describeConviction } from "@/lib/conviction";
import { fmtCurrency } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { Briefing } from "@/lib/types";

export function DecisionCard({
  briefing,
  currency,
}: {
  briefing: Briefing;
  currency: string;
}) {
  const conviction = describeConviction(briefing);
  const plan = briefing.action_plan;
  const hasLevels =
    !!plan &&
    (plan.entry_limit !== null ||
      plan.stop_loss !== null ||
      plan.take_profit_1 !== null);

  return (
    <section
      aria-label="Decision summary"
      className="fade-up rounded-xl border bg-card p-5 md:p-6"
    >
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="flex flex-wrap items-center gap-3">
          <SignalBadge signal={briefing.overall_signal} size="xl" />
          <div className="flex flex-col gap-1">
            <span className="text-sm font-medium text-foreground">{conviction.phrase}</span>
            <AgreementRow
              agreeing={conviction.agreement.agreeing}
              total={conviction.agreement.total}
              convergencePct={Math.round(briefing.conviction.signal_convergence * 100)}
            />
          </div>
        </div>
        {plan?.horizon && (
          <div className="text-right">
            <div className="text-[11px] font-medium text-muted-foreground">Horizon</div>
            <div className="mt-0.5 text-sm text-foreground">{plan.horizon}</div>
          </div>
        )}
      </div>

      <div className="my-5 border-t" />

      {hasLevels ? (
        <LevelsRow
          plan={plan!}
          currency={currency}
          riskReward={briefing.risk_assessment.risk_reward_ratio}
        />
      ) : (
        <WatchForCallout note={plan?.note ?? null} />
      )}
    </section>
  );
}

function AgreementRow({
  agreeing,
  total,
  convergencePct,
}: {
  agreeing: number;
  total: number;
  convergencePct: number;
}) {
  if (total === 0) {
    return (
      <span className="text-xs text-muted-foreground">
        {convergencePct}% signal convergence
      </span>
    );
  }
  return (
    <div className="flex items-center gap-2 text-xs text-muted-foreground">
      <span className="flex items-center gap-1" aria-hidden>
        {Array.from({ length: total }).map((_, i) => (
          <span
            key={i}
            className={cn(
              "inline-block size-1.5 rounded-full",
              i < agreeing ? "bg-foreground" : "bg-muted-foreground/25",
            )}
          />
        ))}
      </span>
      <span>
        <span className="num text-foreground">{agreeing}</span> of{" "}
        <span className="num text-foreground">{total}</span> agents agree
      </span>
    </div>
  );
}

function LevelsRow({
  plan,
  currency,
  riskReward,
}: {
  plan: NonNullable<Briefing["action_plan"]>;
  currency: string;
  riskReward: string | null;
}) {
  return (
    <div>
      <div className="grid grid-cols-3 gap-3 md:gap-4">
        <Level
          icon={<Target className="size-3.5" />}
          label="Entry"
          price={plan.entry_limit}
          rationale={plan.entry_rationale}
          currency={currency}
        />
        <Level
          label="Stop loss"
          price={plan.stop_loss}
          rationale={plan.stop_rationale}
          currency={currency}
        />
        <Level
          label="Target"
          price={plan.take_profit_1}
          secondary={plan.take_profit_2}
          rationale={plan.target_rationale}
          currency={currency}
        />
      </div>
      {(riskReward || plan.note) && (
        <div className="mt-4 flex flex-wrap items-center gap-3 border-t pt-3 text-xs text-muted-foreground">
          {riskReward && (
            <span className="inline-flex items-center gap-2 rounded-full border bg-background px-2.5 py-1">
              <span>Risk / reward</span>
              <span className="num font-medium text-foreground">{riskReward}</span>
            </span>
          )}
          {plan.note && <span className="flex-1">{plan.note}</span>}
        </div>
      )}
    </div>
  );
}

function Level({
  icon,
  label,
  price,
  secondary,
  rationale,
  currency,
}: {
  icon?: React.ReactNode;
  label: string;
  price: number | null;
  secondary?: number | null;
  rationale: string | null;
  currency: string;
}) {
  return (
    <div className="rounded-lg border bg-background p-3 md:p-4">
      <div className="mb-1 flex items-center gap-1.5 text-[11px] font-medium text-muted-foreground">
        {icon}
        {label}
      </div>
      <div className="num text-base font-semibold tracking-tight text-foreground md:text-lg">
        {price !== null ? fmtCurrency(price, currency) : "—"}
      </div>
      {secondary != null && (
        <div className="num mt-0.5 text-[11px] text-muted-foreground">
          then {fmtCurrency(secondary, currency)}
        </div>
      )}
      {rationale && (
        <p className="mt-2 hidden text-xs leading-relaxed text-muted-foreground md:block">
          {rationale}
        </p>
      )}
    </div>
  );
}

function WatchForCallout({ note }: { note: string | null }) {
  return (
    <div className="rounded-lg border border-amber-200 bg-amber-50/60 p-4">
      <div className="mb-1.5 flex items-center gap-2 text-[11px] font-medium text-amber-700">
        <Flag className="size-3.5" />
        Watch for
      </div>
      <p className="text-sm leading-relaxed text-foreground">
        {note ?? "Waiting for a clearer setup — no actionable levels yet."}
      </p>
    </div>
  );
}
