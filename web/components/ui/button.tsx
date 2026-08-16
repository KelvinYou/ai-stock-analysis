import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

/**
 * No shadows: a button separates itself with ground and rule, not elevation.
 * Focus is left to the global `:focus-visible` ring in globals.css — adding a
 * local `outline-none` here would defeat it everywhere at once.
 *
 * Colour here is `action` — "you can click this" — and never `bull`/`bear`,
 * which belong to the data. The one exception is `destructive`, where the
 * warning is the point.
 */
const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded font-medium transition-colors disabled:pointer-events-none disabled:opacity-50 [&_svg]:pointer-events-none [&_svg]:size-4 [&_svg]:shrink-0",
  {
    variants: {
      variant: {
        default: "bg-action text-action-foreground hover:bg-action/90",
        destructive: "bg-bear text-action-foreground hover:bg-bear/90",
        outline: "border bg-card text-ink hover:bg-secondary hover:text-action",
        secondary: "bg-secondary text-ink hover:bg-secondary/70",
        ghost: "text-graphite hover:bg-secondary hover:text-action",
        link: "text-action underline-offset-4 hover:underline",
      },
      size: {
        default: "h-9 px-4 text-sm",
        sm: "h-8 px-3 text-xs",
        lg: "h-10 px-5 text-sm",
        icon: "size-9",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  },
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : "button";
    return <Comp className={cn(buttonVariants({ variant, size, className }))} ref={ref} {...props} />;
  },
);
Button.displayName = "Button";

export { Button, buttonVariants };
