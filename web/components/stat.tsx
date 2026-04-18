import { cn } from "@/lib/utils";

export function Stat({
  label,
  value,
  hint,
  accent,
  className,
}: {
  label: string;
  value: React.ReactNode;
  hint?: React.ReactNode;
  accent?: "up" | "down" | "muted";
  className?: string;
}) {
  return (
    <div className={cn("flex flex-col gap-1 rounded-lg border border-border/50 bg-muted/20 p-4", className)}>
      <div className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
        {label}
      </div>
      <div
        className={cn(
          "num text-lg font-semibold tracking-tight",
          accent === "up" && "text-emerald-400",
          accent === "down" && "text-rose-400",
          accent === "muted" && "text-muted-foreground",
        )}
      >
        {value}
      </div>
      {hint && <div className="text-xs text-muted-foreground">{hint}</div>}
    </div>
  );
}
