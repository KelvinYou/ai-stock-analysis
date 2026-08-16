import * as React from "react";
import { cn } from "@/lib/utils";

/** Fill colour by role. `neutral` is the default — a bar is chrome until told otherwise. */
const TONE_FILL = {
  neutral: "bg-ink",
  bull: "bg-bull",
  bear: "bg-bear",
} as const;

interface ProgressProps extends React.HTMLAttributes<HTMLDivElement> {
  value: number;
  max?: number;
  indicatorClassName?: string;
  /**
   * Direction of the quantity being drawn. Opt-in: a bar only takes colour
   * when it is measuring something with a direction, and the caller is
   * expected to state that direction in text as well.
   */
  tone?: keyof typeof TONE_FILL;
  /** Announced name for the bar. A meter with no label reads as a stray number. */
  label?: string;
}

/**
 * A bar is a number drawn sideways, so it carries the same ARIA contract as one:
 * `role="progressbar"` plus the value and its bounds. The fill is ink unless a
 * `tone` says the quantity has a direction.
 */
export function Progress({
  value,
  max = 100,
  className,
  indicatorClassName,
  tone = "neutral",
  label,
  ...props
}: ProgressProps) {
  const pct = Math.max(0, Math.min(100, (value / max) * 100));
  return (
    <div
      role="progressbar"
      aria-valuenow={value}
      aria-valuemin={0}
      aria-valuemax={max}
      aria-label={label}
      className={cn("relative h-1.5 w-full overflow-hidden rounded-full bg-muted", className)}
      {...props}
    >
      <div
        className={cn(
          "h-full rounded-full transition-all",
          TONE_FILL[tone],
          indicatorClassName,
        )}
        style={{ width: `${pct}%` }}
      />
    </div>
  );
}
