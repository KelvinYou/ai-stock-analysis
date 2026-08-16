import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";

export default function NotFound() {
  return (
    <Card className="mx-auto max-w-xl p-10 text-center md:p-12">
      <p className="eyebrow">404</p>
      <h2 className="mt-2 text-lg font-semibold tracking-[-0.02em] text-ink [font-stretch:125%] md:text-xl">
        Ticker not found
      </h2>
      <p className="mt-2 text-sm text-graphite">
        Run the pipeline to generate its briefing, then check back.
      </p>
      <Button asChild variant="outline" className="mt-6">
        <Link href="/">
          <ArrowLeft className="size-3.5" />
          Back to dashboard
        </Link>
      </Button>
    </Card>
  );
}
