import { cn } from "@/lib/utils";
import { signalLabel } from "@/lib/format";
import type { Confidence, Signal } from "@/lib/types";

const SIGNAL_STYLES: Record<Signal, string> = {
  strong_buy: "bg-emerald-500/15 text-emerald-400 ring-emerald-500/30",
  buy: "bg-emerald-500/10 text-emerald-300 ring-emerald-500/20",
  neutral: "bg-zinc-500/15 text-zinc-300 ring-zinc-500/30",
  sell: "bg-rose-500/10 text-rose-300 ring-rose-500/20",
  strong_sell: "bg-rose-500/15 text-rose-400 ring-rose-500/30",
};

const CONF_STYLES: Record<Confidence, string> = {
  high: "text-emerald-400/80",
  medium: "text-amber-400/80",
  low: "text-zinc-400/80",
};

export function SignalBadge({
  signal,
  confidence,
  size = "md",
  className,
}: {
  signal: Signal;
  confidence?: Confidence;
  size?: "sm" | "md" | "lg";
  className?: string;
}) {
  const sizeCls =
    size === "lg"
      ? "px-3 py-1 text-sm"
      : size === "sm"
        ? "px-1.5 py-0.5 text-[10px]"
        : "px-2 py-0.5 text-xs";
  return (
    <div className={cn("inline-flex items-center gap-2", className)}>
      <span
        className={cn(
          "inline-flex items-center gap-1.5 rounded-md font-semibold uppercase tracking-wide ring-1 ring-inset",
          SIGNAL_STYLES[signal],
          sizeCls,
        )}
      >
        <Dot signal={signal} />
        {signalLabel(signal)}
      </span>
      {confidence && (
        <span className={cn("text-xs", CONF_STYLES[confidence])}>{confidence} conf.</span>
      )}
    </div>
  );
}

function Dot({ signal }: { signal: Signal }) {
  const color =
    signal === "strong_buy" || signal === "buy"
      ? "bg-emerald-400"
      : signal === "strong_sell" || signal === "sell"
        ? "bg-rose-400"
        : "bg-zinc-400";
  return (
    <span className="relative flex size-1.5">
      <span className={cn("absolute inline-flex h-full w-full animate-ping rounded-full opacity-60", color)} />
      <span className={cn("relative inline-flex h-full w-full rounded-full", color)} />
    </span>
  );
}
