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
      ? "Strong Conviction: Buy"
      : clamped > 0.15
        ? "Leaning Buy"
        : clamped < -0.5
          ? "Strong Conviction: Sell"
          : clamped < -0.15
            ? "Leaning Sell"
            : "Neutral";
  const barColor = clamped > 0 ? "bg-emerald-500" : clamped < 0 ? "bg-rose-500" : "bg-zinc-500";

  return (
    <div className="space-y-3">
      <div className="flex items-baseline justify-between">
        <span className="text-sm text-muted-foreground">{label}</span>
        <span className="num text-2xl font-semibold tracking-tight">
          {clamped >= 0 ? "+" : ""}
          {clamped.toFixed(2)}
        </span>
      </div>
      <div className="relative h-2.5 w-full rounded-full bg-muted">
        <div className="absolute left-1/2 top-0 h-full w-px bg-border" aria-hidden />
        <div
          className={cn("absolute top-0 h-full rounded-full transition-all", barColor)}
          style={{
            left: isLeft ? `${50 - pctFromCenter}%` : "50%",
            width: `${pctFromCenter}%`,
          }}
        />
      </div>
      <div className="flex justify-between text-[11px] text-muted-foreground">
        <span>Strong Sell</span>
        <span>Neutral</span>
        <span>Strong Buy</span>
      </div>
      {convergence != null && (
        <div className="pt-1 text-xs text-muted-foreground">
          Signal convergence:{" "}
          <span className="text-foreground num">{(convergence * 100).toFixed(0)}%</span>
        </div>
      )}
    </div>
  );
}
