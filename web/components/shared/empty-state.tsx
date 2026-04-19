export function EmptyState() {
  return (
    <div className="rounded-xl border bg-card p-10 text-center md:p-14">
      <h2 className="text-lg font-semibold tracking-tight text-foreground md:text-xl">
        No briefings yet
      </h2>
      <p className="mx-auto mt-2 max-w-md text-sm text-muted-foreground">
        Generate your first briefing and it will appear here.
      </p>
      <code className="mt-5 inline-block rounded-md border bg-muted px-3 py-2 font-mono text-xs text-foreground">
        stock-analysis AAPL --market US --rounds 3
      </code>
    </div>
  );
}
