import { cn } from "@/lib/utils";
import { signalLabel } from "@/lib/format";
import type { Confidence, Signal } from "@/lib/types";

const SIGNAL_STYLES: Record<Signal, string> = {
  strong_buy: "bg-emerald-50 text-emerald-700 border-emerald-200",
  buy: "bg-emerald-50/60 text-emerald-700 border-emerald-200/70",
  neutral: "bg-muted text-foreground/80 border-border",
  sell: "bg-rose-50/60 text-rose-700 border-rose-200/70",
  strong_sell: "bg-rose-50 text-rose-700 border-rose-200",
};

const CONF_STYLES: Record<Confidence, string> = {
  high: "text-emerald-600",
  medium: "text-amber-600",
  low: "text-muted-foreground",
};

export function SignalBadge({
  signal,
  confidence,
  size = "md",
  className,
}: {
  signal: Signal;
  confidence?: Confidence;
  size?: "sm" | "md" | "lg" | "xl";
  className?: string;
}) {
  const sizeCls =
    size === "xl"
      ? "px-3 py-1.5 text-xs"
      : size === "lg"
        ? "px-2.5 py-1 text-[11px]"
        : size === "sm"
          ? "px-2 py-0.5 text-[10px]"
          : "px-2 py-0.5 text-[11px]";
  return (
    <div className={cn("inline-flex items-center gap-2", className)}>
      <span
        className={cn(
          "inline-flex items-center gap-1.5 rounded-full border font-medium",
          SIGNAL_STYLES[signal],
          sizeCls,
        )}
      >
        <Dot signal={signal} size={size} />
        {signalLabel(signal)}
      </span>
      {confidence && (
        <span className={cn("text-[11px] font-medium", CONF_STYLES[confidence])}>
          {confidence} conf.
        </span>
      )}
    </div>
  );
}

function Dot({ signal, size }: { signal: Signal; size: "sm" | "md" | "lg" | "xl" }) {
  const color =
    signal === "strong_buy" || signal === "buy"
      ? "bg-emerald-500"
      : signal === "strong_sell" || signal === "sell"
        ? "bg-rose-500"
        : "bg-zinc-400";
  const dotSize = size === "xl" ? "size-1.5" : "size-1";
  return <span className={cn("inline-block rounded-full", dotSize, color)} aria-hidden />;
}
