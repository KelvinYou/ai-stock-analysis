export function EmptyState() {
  return (
    <div className="relative overflow-hidden rounded-sm border hairline bg-card/40 p-14 text-center">
      <div className="absolute inset-0 grid-lines opacity-40" aria-hidden />
      <div className="relative">
        <p className="display text-sm uppercase tracking-[0.3em] text-primary">
          No briefings on wire
        </p>
        <h2 className="display mx-auto mt-4 max-w-lg text-2xl italic tracking-tight text-foreground md:text-3xl">
          &ldquo;The tape has nothing to say &mdash; yet.&rdquo;
        </h2>
        <p className="mx-auto mt-6 max-w-xl text-sm text-muted-foreground">
          Generate your first briefing and it will appear on the desk. From your terminal:
        </p>
        <code className="mt-5 inline-block rounded-sm border hairline bg-muted/60 px-3 py-2 font-mono text-xs text-foreground/90">
          stock-analysis AAPL --market US --rounds 3
        </code>
      </div>
    </div>
  );
}
