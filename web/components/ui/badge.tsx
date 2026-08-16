import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

/**
 * Neutral by default — a badge separates itself from its surroundings with
 * weight and ground. The `bull` / `bear` / `halt` variants exist for the cases
 * where the badge *is* the datum (direction, caution); they tint the ground and
 * the rule, never the text, so the label stays the thing you read.
 */
const badgeVariants = cva(
  "inline-flex items-center rounded border px-2 py-0.5 text-micro font-semibold uppercase tracking-[0.07em]",
  {
    variants: {
      variant: {
        default: "border-transparent bg-ink text-primary-foreground",
        secondary: "border-transparent bg-secondary text-ink",
        destructive: "border-bear bg-transparent text-bear",
        outline: "text-graphite",
        bull: "border-bull/30 bg-bull/10 text-bull",
        bear: "border-bear/30 bg-bear/10 text-bear",
        halt: "border-halt/30 bg-halt/10 text-halt",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  },
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return <div className={cn(badgeVariants({ variant }), className)} {...props} />;
}

export { Badge, badgeVariants };
