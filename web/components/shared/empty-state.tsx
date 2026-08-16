import { Card } from "@/components/ui/card";

export function EmptyState() {
  return (
    <Card className="p-10 text-center md:p-14">
      <h2 className="text-lg font-semibold tracking-[-0.02em] text-ink [font-stretch:125%] md:text-xl">
        No briefings yet
      </h2>
      <p className="mx-auto mt-2 max-w-md text-sm text-graphite">
        Generate your first briefing and it will appear here.
      </p>
      <code className="num mt-5 inline-block rounded border bg-muted px-3 py-2 text-xs text-ink">
        stock-analysis AAPL --market US --rounds 3
      </code>
    </Card>
  );
}
