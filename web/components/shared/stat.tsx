import { cn } from "@/lib/utils";

/**
 * A measured reading. `accent` repaints the number *and* sets a ▲/▼ glyph beside
 * it — the glyph is what a colour-blind reader goes by, so it stays whether or
 * not the hue lands.
 */
const ACCENT_GLYPH = { up: "▲", down: "▼", muted: null } as const;
const ACCENT_COLOR = {
  up: "text-bull",
  down: "text-bear",
  muted: "text-graphite",
} as const;

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
  const glyph = accent ? ACCENT_GLYPH[accent] : null;
  return (
    <div
      className={cn(
        "flex flex-col gap-1.5 rounded-lg border bg-background p-4 transition-colors hover:bg-secondary",
        className,
      )}
    >
      <div className="eyebrow">{label}</div>
      <div
        className={cn(
          "num flex items-baseline gap-1.5 text-lg font-semibold leading-tight tracking-tight",
          accent ? ACCENT_COLOR[accent] : "text-ink",
        )}
      >
        {glyph && (
          <span className="text-mini leading-none" aria-hidden>
            {glyph}
          </span>
        )}
        <span>{value}</span>
      </div>
      {hint && <div className="text-micro leading-snug text-graphite">{hint}</div>}
    </div>
  );
}
