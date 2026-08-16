import { ConsensusAxis } from "@/components/consensus/consensus-axis";
import { DIRECTION_LABEL, TONE_EYEBROW, describeConviction } from "@/lib/conviction";
import { fmtCurrency } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { Briefing } from "@/lib/types";

// Hold stays ink: a neutral verdict is a complete result, not a weak one, and
// greying it out would read as "no answer yet".
const VERDICT_TONE = {
  bull: "text-bull",
  bear: "text-bear",
  neutral: "text-ink",
} as const;

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
      aria-label="Decision"
      className="fade-up overflow-hidden rounded-lg border bg-card"
    >
      <div className="grid items-center gap-8 p-6 md:grid-cols-[minmax(0,17rem)_minmax(0,1fr)] md:gap-12 md:p-8">
        <div>
          <p className="eyebrow">{TONE_EYEBROW[conviction.tone]}</p>
          <p
            className={cn(
              "mt-2 text-5xl font-semibold leading-[0.95] tracking-[-0.03em] [font-stretch:125%] md:text-6xl",
              VERDICT_TONE[conviction.agreement.direction],
            )}
          >
            {DIRECTION_LABEL[conviction.agreement.direction]}
          </p>
          {conviction.agreement.total > 0 && (
            <p className="mt-3 text-sm text-graphite">
              <span className="num text-ink">{conviction.agreement.agreeing}</span> of{" "}
              <span className="num text-ink">{conviction.agreement.total}</span> desks
              back it
            </p>
          )}
          {plan?.horizon && (
            <p className="mt-5 border-t pt-3 text-xs text-graphite">
              Horizon <span className="text-ink">{plan.horizon}</span>
            </p>
          )}
        </div>

        <ConsensusAxis briefing={briefing} />
      </div>

      <div className="border-t bg-paper/60 px-6 py-5 md:px-8">
        {hasLevels ? (
          <Levels
            plan={plan!}
            currency={currency}
            riskReward={briefing.risk_assessment.risk_reward_ratio}
          />
        ) : (
          <Withheld note={plan?.note ?? null} />
        )}
      </div>
    </section>
  );
}

function Levels({
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
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <h3 className="eyebrow">Levels</h3>
        {riskReward && (
          <span className="text-micro text-graphite">
            Risk / reward <span className="num text-ink">{riskReward}</span>
          </span>
        )}
      </div>
      <dl className="mt-3 grid gap-x-6 gap-y-4 sm:grid-cols-3">
        <Level label="Entry" price={plan.entry_limit} rationale={plan.entry_rationale} currency={currency} />
        <Level label="Stop" price={plan.stop_loss} rationale={plan.stop_rationale} currency={currency} />
        <Level
          label="Target"
          price={plan.take_profit_1}
          secondary={plan.take_profit_2}
          rationale={plan.target_rationale}
          currency={currency}
        />
      </dl>
    </div>
  );
}

function Level({
  label,
  price,
  secondary,
  rationale,
  currency,
}: {
  label: string;
  price: number | null;
  secondary?: number | null;
  rationale: string | null;
  currency: string;
}) {
  return (
    <div>
      <dt className="text-micro uppercase tracking-[0.07em] text-graphite">{label}</dt>
      <dd className="num mt-1 text-xl font-medium text-ink">
        {price !== null ? fmtCurrency(price, currency) : "—"}
        {secondary != null && (
          <span className="ml-2 text-xs text-graphite">
            then {fmtCurrency(secondary, currency)}
          </span>
        )}
      </dd>
      {rationale && <p className="prose-claim mt-1.5 text-xs">{rationale}</p>}
    </div>
  );
}

function Withheld({ note }: { note: string | null }) {
  return (
    // `halt` is axis chroma: this is the axis's withheld state, restated where
    // the levels would otherwise be.
    <div className="border-l-2 border-halt pl-4">
      <h3 className="text-micro font-semibold uppercase tracking-[0.07em] text-halt">
        No levels quoted
      </h3>
      <p className="prose-claim mt-1 text-sm">
        {note ??
          "The desks are too far apart to place an entry, stop, or target. Wait for them to converge."}
      </p>
    </div>
  );
}
