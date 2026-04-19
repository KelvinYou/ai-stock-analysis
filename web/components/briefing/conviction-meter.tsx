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
      ? "Strong conviction · Buy"
      : clamped > 0.15
        ? "Leaning buy"
        : clamped < -0.5
          ? "Strong conviction · Sell"
          : clamped < -0.15
            ? "Leaning sell"
            : "Neutral";
  const barColor =
    clamped > 0 ? "bg-emerald-500" : clamped < 0 ? "bg-rose-500" : "bg-zinc-400";
  const tone =
    clamped > 0.15
      ? "text-emerald-600"
      : clamped < -0.15
        ? "text-rose-600"
        : "text-muted-foreground";

  return (
    <div className="space-y-4">
      <div>
        <div className="text-[11px] font-medium text-muted-foreground">Score</div>
        <div className="mt-1 flex items-baseline gap-2">
          <span
            className={cn(
              "num text-2xl font-semibold leading-none tracking-tight",
              tone,
            )}
          >
            {clamped >= 0 ? "+" : ""}
            {clamped.toFixed(2)}
          </span>
          <span className="text-xs text-muted-foreground">/ 1.00</span>
        </div>
        <p className={cn("mt-1.5 text-sm font-medium", tone)}>{label}</p>
      </div>

      <div>
        <div className="relative h-1 w-full overflow-hidden rounded-full bg-muted">
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
        <div className="mt-1.5 flex justify-between text-[10px] text-muted-foreground">
          <span>Sell</span>
          <span>Neutral</span>
          <span>Buy</span>
        </div>
      </div>

      {convergence != null && (
        <div className="border-t pt-3">
          <div className="flex items-center justify-between text-[11px] text-muted-foreground">
            <span>Signal convergence</span>
            <span className="num text-foreground">{(convergence * 100).toFixed(0)}%</span>
          </div>
          <div className="mt-1.5 h-1 w-full overflow-hidden rounded-full bg-muted">
            <span
              className="block h-full rounded-full bg-foreground/80 transition-all duration-500"
              style={{ width: `${convergence * 100}%` }}
            />
          </div>
        </div>
      )}
    </div>
  );
}
