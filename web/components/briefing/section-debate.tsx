import { TrendingDown, TrendingUp } from "lucide-react";
import { SectionCard } from "@/components/shared/section-card";
import type { DebateArgument, DebateResult } from "@/lib/types";

export function DebateSection({ data }: { data: DebateResult }) {
  return (
    <SectionCard
      id="debate"
      title="The debate"
      description={`${data.rounds.length} adversarial rounds`}
    >
      <div className="grid gap-3 md:grid-cols-2">
        <CaseSummary tone="bull" title="Bull case" text={data.bull_case_summary} />
        <CaseSummary tone="bear" title="Bear case" text={data.bear_case_summary} />
      </div>

      <div className="relative mt-8 space-y-6 border-l pl-6">
        {data.rounds.map((r) => (
          <div key={r.round_number} className="relative">
            <span
              className="absolute -left-[25px] top-2 size-2 rounded-full bg-foreground/70 ring-4 ring-background"
              aria-hidden
            />
            <div className="mb-3 text-[11px] font-medium text-muted-foreground">
              Round {r.round_number}
            </div>
            <div className="grid gap-3 md:grid-cols-2">
              <Argument tone="bull" arg={r.bull_argument} />
              <Argument tone="bear" arg={r.bear_argument} />
            </div>
          </div>
        ))}
      </div>

      <div className="mt-8 grid gap-3 md:grid-cols-3">
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
  const cls =
    tone === "bull"
      ? "border-emerald-200 bg-emerald-50/50"
      : "border-rose-200 bg-rose-50/50";
  const titleCls = tone === "bull" ? "text-emerald-700" : "text-rose-700";
  return (
    <article className={`rounded-lg border ${cls} p-4`}>
      <div className={`mb-1.5 flex items-center gap-1.5 ${titleCls}`}>
        <Icon className="size-3.5" />
        <h3 className="text-[11px] font-semibold">{title}</h3>
      </div>
      <p className="text-sm leading-relaxed text-foreground">{text}</p>
    </article>
  );
}

function Argument({ tone, arg }: { tone: "bull" | "bear"; arg: DebateArgument }) {
  const titleCls = tone === "bull" ? "text-emerald-700" : "text-rose-700";
  return (
    <div className="rounded-lg border bg-background p-4">
      <div className={`mb-1.5 text-[11px] font-semibold ${titleCls}`}>
        {tone === "bull" ? "Bull" : "Bear"}
      </div>
      <p className="text-sm leading-relaxed text-foreground">{arg.argument}</p>
      {arg.key_points.length > 0 && (
        <ul className="mt-3 space-y-1 border-t pt-3 text-sm">
          {arg.key_points.map((p, i) => (
            <li key={i} className="flex gap-2 text-muted-foreground">
              <span className={titleCls}>›</span>
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
  const accent =
    tone === "warn"
      ? "text-amber-700"
      : tone === "neutral"
        ? "text-emerald-700"
        : "text-muted-foreground";
  return (
    <div className="rounded-lg border bg-background p-4">
      <h4 className={`mb-2 text-[11px] font-semibold ${accent}`}>{title}</h4>
      {items.length > 0 ? (
        <ul className="space-y-1.5 text-sm">
          {items.map((t, idx) => (
            <li key={idx} className="flex gap-2 leading-relaxed">
              <span className="text-muted-foreground">—</span>
              <span>{t}</span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-sm text-muted-foreground">None</p>
      )}
    </div>
  );
}
