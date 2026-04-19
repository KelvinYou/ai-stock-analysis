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
        "flex flex-col gap-1.5 rounded-lg border bg-background p-4 transition-colors hover:bg-muted/40",
        className,
      )}
    >
      <div className="text-[11px] font-medium text-muted-foreground">{label}</div>
      <div
        className={cn(
          "num text-lg font-semibold leading-tight tracking-tight text-foreground",
          accent === "up" && "text-emerald-600",
          accent === "down" && "text-rose-600",
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
