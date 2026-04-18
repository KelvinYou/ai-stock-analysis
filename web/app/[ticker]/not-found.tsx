import Link from "next/link";

export default function NotFound() {
  return (
    <div className="mx-auto max-w-md rounded-xl border border-border/60 bg-card/60 p-10 text-center">
      <h2 className="text-2xl font-semibold tracking-tight">Ticker not found</h2>
      <p className="mt-2 text-muted-foreground">
        This ticker hasn&rsquo;t been analyzed yet. Run the pipeline to generate its data.
      </p>
      <Link
        href="/"
        className="mt-6 inline-flex items-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90"
      >
        Back to tickers
      </Link>
    </div>
  );
}
