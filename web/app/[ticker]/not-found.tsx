import Link from "next/link";
import { ArrowLeft } from "lucide-react";

export default function NotFound() {
  return (
    <div className="mx-auto max-w-xl rounded-xl border bg-card p-10 text-center md:p-12">
      <p className="text-xs font-medium text-muted-foreground">404</p>
      <h2 className="mt-2 text-lg font-semibold tracking-tight text-foreground md:text-xl">
        Ticker not found
      </h2>
      <p className="mt-2 text-sm text-muted-foreground">
        Run the pipeline to generate its briefing, then check back.
      </p>
      <Link
        href="/"
        className="mt-6 inline-flex items-center gap-2 rounded-md border bg-background px-3.5 py-2 text-sm font-medium transition-colors hover:bg-muted"
      >
        <ArrowLeft className="size-3.5" />
        Back to dashboard
      </Link>
    </div>
  );
}
