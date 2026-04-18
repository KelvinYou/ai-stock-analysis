import { TrendingDown, TrendingUp } from "lucide-react";
import { SectionCard } from "@/components/shared/section-card";
import type { DebateArgument, DebateResult } from "@/lib/types";

export function DebateSection({ data }: { data: DebateResult }) {
  return (
    <SectionCard
      id="debate"
      chapter="04"
      title="The Debate"
      description={`${data.rounds.length} adversarial rounds · consensus synthesized below`}
    >
      <div className="grid gap-4 md:grid-cols-2">
        <CaseSummary tone="bull" title="Bull case" text={data.bull_case_summary} />
        <CaseSummary tone="bear" title="Bear case" text={data.bear_case_summary} />
      </div>

      <div className="relative mt-10 space-y-6 border-l hairline pl-8">
        <span
          className="absolute -left-[7px] top-0 size-3.5 rounded-full border-2 border-primary bg-background"
          aria-hidden
        />
        <span
          className="absolute -left-[5px] bottom-0 size-2 rounded-full bg-muted-foreground/40"
          aria-hidden
        />
        {data.rounds.map((r) => (
          <div key={r.round_number} className="relative">
            <span
              className="absolute -left-[33px] top-2 size-2 rounded-full bg-primary/60 ring-4 ring-background"
              aria-hidden
            />
            <div className="mb-4 flex items-baseline gap-3">
              <span className="num text-[10px] uppercase tracking-[0.26em] text-primary">
                Round {String(r.round_number).padStart(2, "0")}
              </span>
              <span className="ruler flex-1 max-w-[120px]" />
            </div>
            <div className="grid gap-5 md:grid-cols-2">
              <Argument tone="bull" arg={r.bull_argument} />
              <Argument tone="bear" arg={r.bear_argument} />
            </div>
          </div>
        ))}
      </div>

      <div className="mt-10 grid gap-4 md:grid-cols-3">
        <ListBox
          title="Agreements"
          items={data.key_points_of_agreement}
          tone="neutral"
          symbol="="
        />
        <ListBox
          title="Disagreements"
          items={data.key_points_of_disagreement}
          tone="warn"
          symbol="≠"
        />
        <ListBox
          title="Unresolved"
          items={data.unresolved_uncertainties}
          tone="muted"
          symbol="?"
        />
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
  const accent = tone === "bull" ? "text-emerald-300" : "text-rose-300";
  const bar = tone === "bull" ? "before:bg-emerald-400" : "before:bg-rose-400";
  return (
    <article
      className={`relative overflow-hidden rounded-sm border hairline bg-background/40 p-5 before:absolute before:left-0 before:top-0 before:h-full before:w-[3px] ${bar}`}
    >
      <div className={`mb-2 flex items-center gap-2 ${accent}`}>
        <Icon className="size-4" />
        <h3 className="text-[10px] font-semibold uppercase tracking-[0.26em]">{title}</h3>
      </div>
      <p className="display text-base leading-relaxed text-foreground/95">{text}</p>
    </article>
  );
}

function Argument({ tone, arg }: { tone: "bull" | "bear"; arg: DebateArgument }) {
  const accent = tone === "bull" ? "text-emerald-300" : "text-rose-300";
  return (
    <div className="rounded-sm border hairline bg-muted/10 p-4">
      <div className={`mb-2 text-[10px] font-semibold uppercase tracking-[0.26em] ${accent}`}>
        {tone === "bull" ? "Bull" : "Bear"}
      </div>
      <p className="text-sm leading-relaxed text-foreground/95">{arg.argument}</p>
      {arg.key_points.length > 0 && (
        <ul className="mt-3 space-y-1.5 border-t hairline pt-3 text-sm">
          {arg.key_points.map((p, i) => (
            <li key={i} className="flex gap-2 text-muted-foreground">
              <span className={accent}>›</span>
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
  symbol,
}: {
  title: string;
  items: string[];
  tone: "neutral" | "warn" | "muted";
  symbol: string;
}) {
  const border =
    tone === "warn"
      ? "border-amber-500/30"
      : tone === "neutral"
        ? "border-emerald-500/25"
        : "border-border/60";
  const color =
    tone === "warn"
      ? "text-amber-300"
      : tone === "neutral"
        ? "text-emerald-300"
        : "text-muted-foreground";
  return (
    <div className={`rounded-sm border ${border} bg-muted/10 p-4`}>
      <div className="mb-3 flex items-center gap-2">
        <span
          className={`num grid size-6 place-items-center rounded-sm border hairline bg-background/60 text-sm ${color}`}
          aria-hidden
        >
          {symbol}
        </span>
        <h4 className="text-[10px] uppercase tracking-[0.22em] text-muted-foreground/90">
          {title}
        </h4>
      </div>
      {items.length > 0 ? (
        <ul className="space-y-2 text-sm">
          {items.map((t, idx) => (
            <li key={idx} className="flex gap-2 leading-relaxed">
              <span className="text-primary/60">—</span>
              <span>{t}</span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-sm italic text-muted-foreground/70">None</p>
      )}
    </div>
  );
}
