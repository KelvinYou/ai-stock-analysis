import { cn } from "@/lib/utils";

export function ConvictionMeter({
  score,
  convergence,
}: {
  score: number;
  convergence?: number;
}) {
  const clamped = Math.max(-1, Math.min(1, score));
  const pctFromCenter = Math.abs(clamped) * 50;
  const isLeft = clamped < 0;
  const label =
    clamped > 0.5
      ? "Strong Conviction — Buy"
      : clamped > 0.15
        ? "Leaning Buy"
        : clamped < -0.5
          ? "Strong Conviction — Sell"
          : clamped < -0.15
            ? "Leaning Sell"
            : "Neutral";
  const barColor =
    clamped > 0 ? "bg-emerald-400" : clamped < 0 ? "bg-rose-400" : "bg-zinc-500";
  const tone =
    clamped > 0.15
      ? "text-emerald-300"
      : clamped < -0.15
        ? "text-rose-300"
        : "text-muted-foreground";

  return (
    <div className="space-y-4">
      <div>
        <div className="text-[10px] uppercase tracking-[0.22em] text-muted-foreground/80">
          Score
        </div>
        <div className="mt-1 flex items-baseline gap-3">
          <span
            className={cn(
              "num text-4xl font-semibold leading-none tracking-tight",
              tone,
            )}
          >
            {clamped >= 0 ? "+" : ""}
            {clamped.toFixed(2)}
          </span>
          <span className="text-[11px] uppercase tracking-[0.2em] text-muted-foreground">
            / 1.00
          </span>
        </div>
        <p className={cn("mt-2 display italic", tone)}>{label}</p>
      </div>

      <div>
        <div className="relative h-1.5 w-full overflow-hidden rounded-full bg-muted/70">
          <span className="absolute left-1/2 top-0 h-full w-px bg-border" aria-hidden />
          <span
            className={cn(
              "absolute top-0 h-full rounded-full transition-all duration-500",
              barColor,
            )}
            style={{
              left: isLeft ? `${50 - pctFromCenter}%` : "50%",
              width: `${pctFromCenter}%`,
            }}
          />
        </div>
        <div className="mt-2 flex justify-between text-[9px] uppercase tracking-[0.22em] text-muted-foreground/70">
          <span>Sell</span>
          <span>Neutral</span>
          <span>Buy</span>
        </div>
      </div>

      {convergence != null && (
        <div className="border-t hairline pt-3">
          <div className="flex items-center justify-between text-[10px] uppercase tracking-[0.22em] text-muted-foreground/80">
            <span>Signal convergence</span>
            <span className="num text-foreground">{(convergence * 100).toFixed(0)}%</span>
          </div>
          <div className="mt-1.5 h-[3px] w-full overflow-hidden rounded-full bg-muted/70">
            <span
              className="block h-full rounded-full bg-primary/80 transition-all duration-500"
              style={{ width: `${convergence * 100}%` }}
            />
          </div>
        </div>
      )}
    </div>
  );
}
