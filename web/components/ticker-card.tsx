import Link from "next/link";
import { ArrowUpRight } from "lucide-react";
import { Card } from "@/components/ui/card";
import { SignalBadge } from "@/components/signal-badge";
import { fmtCurrency, fmtSignedPercent } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { TickerSummary } from "@/lib/types";

export function TickerCard({ t }: { t: TickerSummary }) {
  const up = (t.priceChangePct ?? 0) >= 0;
  return (
    <Link href={`/${t.symbol}`} className="group block">
      <Card className="relative overflow-hidden p-5 transition-all hover:border-primary/40 hover:bg-card/80 hover:shadow-lg hover:shadow-primary/5">
        <div className="absolute right-4 top-4 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100">
          <ArrowUpRight className="size-4" />
        </div>
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <span className="font-mono text-lg font-bold tracking-tight">{t.symbol}</span>
              <span className="rounded border border-border/60 bg-muted/40 px-1.5 py-0.5 text-[10px] uppercase tracking-wider text-muted-foreground">
                {t.market}
              </span>
            </div>
            <div className="mt-0.5 truncate text-sm text-muted-foreground">{t.name}</div>
          </div>
        </div>
        <div className="mt-4 flex items-end justify-between">
          <div>
            <div className="num text-xl font-semibold tracking-tight">
              {fmtCurrency(t.price, t.currency)}
            </div>
            {t.priceChangePct != null && (
              <div className={cn("num text-xs", up ? "text-emerald-400" : "text-rose-400")}>
                {fmtSignedPercent(t.priceChangePct)} today
              </div>
            )}
          </div>
          {t.signal && <SignalBadge signal={t.signal} size="sm" />}
        </div>
        {t.sector && (
          <div className="mt-3 border-t border-border/50 pt-3 text-xs text-muted-foreground">
            {t.sector}
          </div>
        )}
      </Card>
    </Link>
  );
}
