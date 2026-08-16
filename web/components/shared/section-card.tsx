import { cn } from "@/lib/utils";

/**
 * Two tiers, because the ticker page carries two kinds of content.
 *
 * `reference` — computed readings the pipeline measured. Bordered, dense, quiet.
 * `argument`  — reasoning a model produced. Unboxed, wider measure, more air,
 *               so prose reads as prose rather than as another data tile.
 *
 * `layer` takes the pipeline layer the section came from. It is a real ordinal
 * from the architecture, not decoration: it tells the reader where in the
 * evidence chain they are.
 */
export function SectionCard({
  id,
  layer,
  title,
  description,
  action,
  children,
  className,
  tier = "reference",
  flush,
}: {
  id?: string;
  layer?: string;
  title: string;
  description?: string;
  action?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
  tier?: "reference" | "argument";
  flush?: boolean;
}) {
  const argument = tier === "argument";

  return (
    <section id={id} className={cn("scroll-mt-28", className)}>
      <header
        className={cn(
          "flex flex-wrap items-end justify-between gap-x-6 gap-y-2",
          argument ? "mb-6 border-t-2 border-ink pt-4" : "mb-3",
        )}
      >
        <div className="min-w-0">
          {layer && <p className="eyebrow mb-1.5">{layer}</p>}
          <h2
            className={cn(
              "font-semibold tracking-[-0.02em] text-ink [font-stretch:125%]",
              argument ? "text-2xl md:text-3xl" : "text-base",
            )}
          >
            {title}
          </h2>
          {description && (
            <p className={cn("text-graphite", argument ? "mt-2 max-w-prose text-sm" : "mt-1 text-micro")}>
              {description}
            </p>
          )}
        </div>
        {action}
      </header>
      <div
        className={cn(
          !argument && cn("rounded-lg border bg-card", flush ? "p-0" : "p-5"),
        )}
      >
        {children}
      </div>
    </section>
  );
}
