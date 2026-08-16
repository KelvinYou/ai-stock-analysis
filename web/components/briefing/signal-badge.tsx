import { cn } from "@/lib/utils";
import { signalLabel } from "@/lib/format";
import { signalGlyph } from "@/lib/signal-display";
import type { Confidence, Signal } from "@/lib/types";

/**
 * Direction reads three ways at once: the glyph, the word, and the hue. Colour
 * is the last of the three to arrive and the first thing a colour-blind reader
 * loses, so the glyph and the label are never dropped in its favour. The glyph
 * map is shared with the screener via `lib/signal-display`.
 *
 * Text colour only — the client asked for a coloured word, not a filled pill,
 * and a tinted chip at list density would fight the consensus axis.
 */
const SIZE_CLS = {
  sm: "text-mini",
  md: "text-micro",
  lg: "text-micro",
  xl: "text-xs",
} as const;

const SIGNAL_CLS: Record<Signal, string> = {
  strong_buy: "text-bull",
  buy: "text-bull",
  neutral: "text-graphite",
  sell: "text-bear",
  strong_sell: "text-bear",
};

/** Conviction in the reading itself — `halt` at medium, unmarked at low. */
const CONFIDENCE_CLS: Record<Confidence, string> = {
  high: "text-bull",
  medium: "text-halt",
  low: "text-graphite",
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
  return (
    <div className={cn("inline-flex items-baseline gap-2", className)}>
      <span
        className={cn(
          "inline-flex items-baseline gap-1.5 uppercase [font-stretch:125%]",
          // At list density the badge repeats 26 times — it labels, it should
          // not shout. Weight and tracking open up only at the detail sizes.
          size === "sm" || size === "md"
            ? "font-medium tracking-[0.06em]"
            : "font-semibold tracking-[0.09em]",
          SIZE_CLS[size],
          SIGNAL_CLS[signal],
        )}
      >
        <span aria-hidden className="tracking-normal">
          {signalGlyph(signal)}
        </span>
        {signalLabel(signal)}
      </span>
      {confidence && (
        <span className={cn("text-micro", CONFIDENCE_CLS[confidence])}>
          {confidence} conf.
        </span>
      )}
    </div>
  );
}
