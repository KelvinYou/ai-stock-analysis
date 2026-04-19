import { cn } from "@/lib/utils";

export function SectionCard({
  id,
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
      <header className="mb-4 flex flex-wrap items-end justify-between gap-3">
        <div className="min-w-0">
          <h2 className="text-base font-semibold tracking-tight text-foreground md:text-lg">
            {title}
          </h2>
          {description && (
            <p className="mt-1 text-xs text-muted-foreground">{description}</p>
          )}
        </div>
        {action}
      </header>
      <div
        className={cn(
          "rounded-xl border bg-card",
          flush ? "p-0" : "p-5 md:p-6",
        )}
      >
        {children}
      </div>
    </section>
  );
}
