import { cn } from "@/lib/utils";

export function SectionCard({
  id,
  chapter,
  title,
  description,
  action,
  children,
  className,
  flush,
}: {
  id?: string;
  chapter?: string;
  title: string;
  description?: string;
  action?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
  flush?: boolean;
}) {
  return (
    <section id={id} className={cn("scroll-mt-24", className)}>
      <header className="mb-6 flex flex-wrap items-end justify-between gap-4 border-b hairline pb-4">
        <div className="flex items-baseline gap-4">
          {chapter && (
            <span className="num shrink-0 text-xs uppercase tracking-[0.24em] text-primary">
              § {chapter}
            </span>
          )}
          <div>
            <h2 className="display text-2xl leading-tight tracking-tight md:text-3xl">
              {title}
            </h2>
            {description && (
              <p className="mt-1.5 text-sm text-muted-foreground">{description}</p>
            )}
          </div>
        </div>
        {action}
      </header>
      <div className={cn("rounded-sm border hairline bg-card/40", flush ? "p-0" : "p-6 md:p-8")}>
        {children}
      </div>
    </section>
  );
}
