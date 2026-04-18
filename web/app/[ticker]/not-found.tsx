import Link from "next/link";
import { ArrowLeft } from "lucide-react";

export default function NotFound() {
  return (
    <div className="mx-auto max-w-xl rounded-sm border hairline bg-card/40 p-12 text-center">
      <p className="display text-xs uppercase tracking-[0.3em] text-primary">404 · Off-tape</p>
      <h2 className="display mt-3 text-3xl italic tracking-tight">
        This ticker hasn&rsquo;t crossed the wire.
      </h2>
      <p className="mt-4 text-sm text-muted-foreground">
        Run the pipeline to generate its briefing, then check back.
      </p>
      <Link
        href="/"
        className="mt-7 inline-flex items-center gap-2 rounded-sm border hairline bg-muted/40 px-4 py-2 text-sm transition-colors hover:bg-muted"
      >
        <ArrowLeft className="size-3.5" />
        Back to the desk
      </Link>
    </div>
  );
}
