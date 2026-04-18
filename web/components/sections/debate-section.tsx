import { TrendingDown, TrendingUp } from "lucide-react";
import { SectionCard } from "./section-card";
import type { DebateArgument, DebateResult } from "@/lib/types";

export function DebateSection({ data }: { data: DebateResult }) {
  return (
    <SectionCard
      id="debate"
      title="Bull vs Bear debate"
      description={`${data.rounds.length} adversarial rounds · consensus synthesized below`}
    >
      <div className="grid gap-4 md:grid-cols-2">
        <CaseSummary tone="bull" title="Bull case" text={data.bull_case_summary} />
        <CaseSummary tone="bear" title="Bear case" text={data.bear_case_summary} />
      </div>

      <div className="mt-8 space-y-6">
        {data.rounds.map((r) => (
          <div key={r.round_number} className="rounded-xl border border-border/50 bg-muted/10 p-5">
            <div className="mb-4 flex items-center gap-3">
              <span className="rounded-md bg-primary/15 px-2 py-0.5 text-xs font-medium uppercase tracking-wider text-primary">
                Round {r.round_number}
              </span>
            </div>
            <div className="grid gap-4 md:grid-cols-2">
              <Argument tone="bull" arg={r.bull_argument} />
              <Argument tone="bear" arg={r.bear_argument} />
            </div>
          </div>
        ))}
      </div>

      <div className="mt-8 grid gap-4 md:grid-cols-3">
        <ListBox title="Agreements" items={data.key_points_of_agreement} tone="neutral" />
        <ListBox title="Disagreements" items={data.key_points_of_disagreement} tone="warn" />
        <ListBox title="Unresolved" items={data.unresolved_uncertainties} tone="muted" />
      </div>
    </SectionCard>
  );
}

function CaseSummary({
  tone,
  title,
  text,
}: {
  tone: "bull" | "bear";
  title: string;
  text: string;
}) {
  const Icon = tone === "bull" ? TrendingUp : TrendingDown;
  const tintClass =
    tone === "bull"
      ? "border-emerald-500/30 bg-emerald-500/5"
      : "border-rose-500/30 bg-rose-500/5";
  const iconClass = tone === "bull" ? "text-emerald-400" : "text-rose-400";
  return (
    <div className={`rounded-xl border p-5 ${tintClass}`}>
      <div className="mb-2 flex items-center gap-2">
        <Icon className={`size-4 ${iconClass}`} />
        <h3 className="text-sm font-semibold uppercase tracking-wider">{title}</h3>
      </div>
      <p className="text-sm leading-relaxed text-foreground/90">{text}</p>
    </div>
  );
}

function Argument({ tone, arg }: { tone: "bull" | "bear"; arg: DebateArgument }) {
  const color = tone === "bull" ? "text-emerald-400" : "text-rose-400";
  return (
    <div>
      <div className={`mb-2 text-[11px] font-semibold uppercase tracking-wider ${color}`}>
        {tone === "bull" ? "Bull" : "Bear"}
      </div>
      <p className="text-sm leading-relaxed">{arg.argument}</p>
      {arg.key_points.length > 0 && (
        <ul className="mt-3 space-y-1 text-sm text-muted-foreground">
          {arg.key_points.map((p, i) => (
            <li key={i} className="flex gap-2">
              <span className={color}>›</span>
              <span>{p}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function ListBox({
  title,
  items,
  tone,
}: {
  title: string;
  items: string[];
  tone: "neutral" | "warn" | "muted";
}) {
  const tint =
    tone === "warn"
      ? "border-amber-500/30"
      : tone === "neutral"
        ? "border-border/60"
        : "border-border/40";
  return (
    <div className={`rounded-lg border ${tint} bg-muted/10 p-4`}>
      <h4 className="mb-2 text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
        {title}
      </h4>
      {items.length > 0 ? (
        <ul className="space-y-1.5 text-sm">
          {items.map((i, idx) => (
            <li key={idx}>· {i}</li>
          ))}
        </ul>
      ) : (
        <p className="text-sm text-muted-foreground">None</p>
      )}
    </div>
  );
}
