import { cn } from "@/lib/utils";
import { signalLabel } from "@/lib/format";
import type { Confidence, Signal } from "@/lib/types";

const SIGNAL_STYLES: Record<Signal, string> = {
  strong_buy: "bg-emerald-500/15 text-emerald-300 border-emerald-500/40",
  buy: "bg-emerald-500/8 text-emerald-300/95 border-emerald-500/25",
  neutral: "bg-zinc-500/10 text-zinc-300 border-zinc-500/30",
  sell: "bg-rose-500/8 text-rose-300/95 border-rose-500/25",
  strong_sell: "bg-rose-500/15 text-rose-300 border-rose-500/40",
};

const CONF_STYLES: Record<Confidence, string> = {
  high: "text-emerald-400/80",
  medium: "text-amber-300/80",
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
      ? "px-3 py-1.5 text-[11px] tracking-[0.24em]"
      : size === "sm"
        ? "px-2 py-0.5 text-[9px] tracking-[0.18em]"
        : "px-2.5 py-1 text-[10px] tracking-[0.2em]";
  return (
    <div className={cn("inline-flex items-center gap-2", className)}>
      <span
        className={cn(
          "inline-flex items-center gap-2 rounded-sm border font-semibold uppercase",
          SIGNAL_STYLES[signal],
          sizeCls,
        )}
      >
        <Dot signal={signal} />
        {signalLabel(signal)}
      </span>
      {confidence && (
        <span className={cn("text-[10px] uppercase tracking-[0.2em]", CONF_STYLES[confidence])}>
          {confidence} conf.
        </span>
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
      <span
        className={cn(
          "absolute inline-flex h-full w-full animate-ping rounded-full opacity-50",
          color,
        )}
      />
      <span className={cn("relative inline-flex h-full w-full rounded-full", color)} />
    </span>
  );
}
