import { Card } from "@/components/ui/card";
import { cn } from "@/lib/utils";

export function SectionCard({
  id,
  title,
  description,
  action,
  children,
  className,
}: {
  id?: string;
  title: string;
  description?: string;
  action?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <Card id={id} className={cn("scroll-mt-20 p-6 md:p-8", className)}>
      <div className="mb-5 flex flex-wrap items-baseline justify-between gap-3 border-b border-border/50 pb-4">
        <div>
          <h2 className="text-lg font-semibold tracking-tight">{title}</h2>
          {description && <p className="mt-0.5 text-sm text-muted-foreground">{description}</p>}
        </div>
        {action}
      </div>
      {children}
    </Card>
  );
}
