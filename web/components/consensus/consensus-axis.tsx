import { readConsensus, type AnalystMark, type Direction } from "@/lib/conviction";
import { cn } from "@/lib/utils";
import type { Briefing } from "@/lib/types";

/**
 * The consensus axis.
 *
 * One Sell↔Buy axis carrying the whole pipeline at once. Analyst desks sit
 * above the rule as ticks — the distance between them *is* signal convergence.
 * The conviction the synthesiser reached sits below the rule, read against that
 * spread: inside it when the desks bracket the call, outside it when synthesis
 * went further than any single desk. When the desks scatter, you can see why
 * the briefing has no price levels, instead of reading it in a footnote.
 *
 * The axis is the app's most saturated surface. Direction colour appears on data
 * throughout the UI, but nowhere else does it carry this much of the meaning, so
 * keep surrounding chrome quiet when placing this.
 */

/** −1…+1 → 0…100% across the axis. */
function pct(position: number) {
  return ((position + 1) / 2) * 100;
}

/** Keep end-of-axis labels inside the box instead of bleeding past it. */
function anchor(p: number): React.CSSProperties {
  const left = pct(p);
  const transform =
    left <= 12 ? "translateX(0)" : left >= 88 ? "translateX(-100%)" : "translateX(-50%)";
  return { left: `${left}%`, transform };
}

const TONE: Record<Direction, string> = {
  bull: "text-bull",
  bear: "text-bear",
  neutral: "text-graphite",
};

/** Desks landing on the same signal share one tick, so clustering is visible. */
function cluster(marks: AnalystMark[]) {
  const byPosition = new Map<number, AnalystMark[]>();
  for (const mark of marks) {
    byPosition.set(mark.position, [...(byPosition.get(mark.position) ?? []), mark]);
  }
  return [...byPosition.entries()]
    .map(([position, group]) => ({ position, group }))
    .sort((a, b) => a.position - b.position);
}

function describe(reading: ReturnType<typeof readConsensus>) {
  const desks = reading.marks
    .map((m) => `${m.desk} ${m.signal.replace(/_/g, " ")}`)
    .join(", ");
  const spread = reading.spread
    ? reading.spread.width === 0
      ? "All desks landed on the same signal."
      : `The desks span ${reading.spread.width.toFixed(1)} of the 2.0-wide axis.`
    : "";
  return `Consensus axis, sell to buy. ${desks}. ${spread} Conviction ${reading.conviction.toFixed(2)}, signal convergence ${Math.round(reading.convergence * 100)} percent.${reading.levelsWithheld ? " Convergence was too low to quote price levels." : ""}`;
}

export function ConsensusAxis({
  briefing,
  className,
}: {
  briefing: Briefing;
  className?: string;
}) {
  const reading = readConsensus(briefing);
  const { spread, conviction, convergence, levelsWithheld } = reading;
  const clusters = cluster(reading.marks);

  const convictionTone =
    conviction > 0.05 ? "bull" : conviction < -0.05 ? "bear" : "neutral";

  return (
    <figure className={cn("m-0", className)}>
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <figcaption className="eyebrow">Four desks read the tape</figcaption>
        <span className="num text-micro text-graphite">
          {Math.round(convergence * 100)}% convergence
        </span>
      </div>

      <div className="relative mt-4 select-none" role="img" aria-label={describe(reading)}>
        {/* Desk labels, then ticks — inputs live above the rule. Adjacent
            clusters alternate rows so neighbouring labels can never collide. */}
        <div className="relative h-11">
          {clusters.map(({ position, group }, i) => (
            <span
              key={position}
              className={cn(
                // Quiet: these are inputs. The conviction mark below the rule
                // is what should carry weight.
                "absolute whitespace-nowrap text-mini font-medium uppercase tracking-[0.06em] [font-stretch:100%]",
                i % 2 === 0 ? "top-0" : "top-[1.15rem]",
                TONE[group[0].direction],
              )}
              style={anchor(position)}
            >
              {group.map((m) => m.abbr).join(" · ")}
            </span>
          ))}
          {/* Leg dropping from each label to the rule. */}
          {clusters.map(({ position, group }, i) => (
            <span
              key={`leg-${position}`}
              className={cn(
                "absolute bottom-0 w-px bg-current opacity-30",
                i % 2 === 0 ? "top-[0.9rem]" : "top-[2.05rem]",
                TONE[group[0].direction],
              )}
              style={{ left: `${pct(position)}%` }}
              aria-hidden
            />
          ))}
        </div>

        <div className="relative h-2.5">
          {clusters.map(({ position, group }) => (
            <span
              key={position}
              className={cn(
                "mark-settle absolute bottom-0 w-0.5 rounded-full bg-current",
                TONE[group[0].direction],
                group.length > 1 ? "h-2.5" : "h-1.5",
              )}
              style={{ left: `${pct(position)}%`, transform: "translateX(-50%)" }}
              aria-hidden
            />
          ))}
        </div>

        {/* The rule, with the spread band drawn through it. */}
        <div className="relative h-px bg-rule">
          <span className="absolute left-1/2 top-1/2 h-2 w-px -translate-x-1/2 -translate-y-1/2 bg-rule" aria-hidden />
          {spread && spread.width > 0 && (
            <span
              className={cn(
                "absolute -top-3 bottom-[-1.75rem] border-x border-dashed",
                levelsWithheld ? "border-halt/60 bg-halt/[0.07]" : "border-graphite/40 bg-graphite/[0.06]",
              )}
              style={{
                left: `${pct(spread.min)}%`,
                width: `${pct(spread.max) - pct(spread.min)}%`,
              }}
              aria-hidden
            />
          )}
        </div>

        {/* Conviction — the output — sits below the rule, inside the spread.
            The heaviest mark on the axis, because it is the answer. */}
        <div className="relative h-7">
          <span
            className={cn(
              "mark-settle absolute top-0 h-7 w-1 origin-top rounded-full bg-current",
              TONE[convictionTone],
            )}
            style={{ left: `${pct(conviction)}%`, transform: "translateX(-50%)" }}
            aria-hidden
          />
        </div>

        <div className="relative h-6">
          <span
            className={cn("num absolute top-0 text-sm font-medium", TONE[convictionTone])}
            style={anchor(conviction)}
          >
            {conviction >= 0 ? "+" : ""}
            {conviction.toFixed(2)}
          </span>
        </div>

        <div className="mt-1 flex justify-between text-mini uppercase tracking-[0.07em] text-graphite">
          <span>Sell</span>
          <span>Neutral</span>
          <span>Buy</span>
        </div>
      </div>
    </figure>
  );
}
