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
    <div
      className={cn(
        "relative flex flex-col gap-2 border-l-2 border-border/40 bg-muted/20 p-4 transition-colors hover:border-primary/60",
        className,
      )}
    >
      <div className="text-[10px] uppercase tracking-[0.22em] text-muted-foreground/80">
        {label}
      </div>
      <div
        className={cn(
          "num text-[22px] font-semibold leading-none tracking-tight",
          accent === "up" && "text-emerald-400",
          accent === "down" && "text-rose-400",
          accent === "muted" && "text-muted-foreground",
        )}
      >
        {value}
      </div>
      {hint && (
        <div className="text-[11px] leading-snug text-muted-foreground">{hint}</div>
      )}
    </div>
  );
}
