import {
  BarChart3,
  ChevronDown,
  Globe,
  Newspaper,
  TrendingUp,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { SectionCard } from "@/components/shared/section-card";
import { SignalBadge } from "./signal-badge";
import { cn } from "@/lib/utils";
import { clampText, fmtNumber, signalLabel } from "@/lib/format";
import { signalPosition } from "@/lib/conviction";
import type { AnalystReports, Confidence, Signal } from "@/lib/types";

/** A named list under a report. `numeric` items are computed, so they set in mono. */
type ListSpec = {
  label: string;
  items: string[];
  tone?: "up" | "down";
  numeric?: boolean;
};

type EvidenceTone = "up" | "down" | "neutral";

type Evidence = {
  label: string;
  text: string;
  tone: EvidenceTone;
};

type DeskDefinition = {
  key: string;
  label: string;
  Icon: LucideIcon;
  signal: Signal;
  confidence: Confidence;
  summary: string;
  evidence: Evidence[];
  rows: Array<[string, string]>;
  lists: ListSpec[];
};

export function AnalystSection({ data }: { data: AnalystReports }) {
  const desks = buildDesks(data);

  return (
    <SectionCard
      id="analysts"
      tier="argument"
      layer="Layer 2 · Four desks"
      title="Specialist desks"
      description="Four analysts read the tape independently"
    >
      <DeskMatrix desks={desks} />
      <DeskNotes desks={desks} />
    </SectionCard>
  );
}

function buildDesks(data: AnalystReports): DeskDefinition[] {
  const fundamentals = data.fundamentals;
  const technical = data.technical;
  const sentiment = data.sentiment;
  const macro = data.macro;

  return [
    {
      key: "fundamentals",
      label: "Fundamentals",
      Icon: BarChart3,
      signal: fundamentals.signal,
      confidence: fundamentals.confidence,
      summary: fundamentals.summary,
      evidence: [
        evidence("Strength", fundamentals.key_strengths[0] ?? fundamentals.margin_analysis, "up"),
        evidence("Risk", fundamentals.key_risks[0] ?? fundamentals.pe_assessment, "down"),
      ],
      rows: [
        ["P/E assessment", fundamentals.pe_assessment],
        ["Margin analysis", fundamentals.margin_analysis],
        ["Debt analysis", fundamentals.debt_analysis],
        ["Growth outlook", fundamentals.growth_outlook],
      ],
      lists: [
        { label: "Key strengths", items: fundamentals.key_strengths, tone: "up" },
        { label: "Key risks", items: fundamentals.key_risks, tone: "down" },
      ],
    },
    {
      key: "technical",
      label: "Technical",
      Icon: TrendingUp,
      signal: technical.signal,
      confidence: technical.confidence,
      summary: technical.summary,
      evidence: [
        evidence(
          "Support",
          technical.support_levels.length
            ? technical.support_levels.slice(0, 2).map((n) => n.toFixed(2)).join(" · ")
            : technical.rsi_assessment,
          "up",
        ),
        evidence(
          "Resistance",
          technical.resistance_levels.length
            ? technical.resistance_levels.slice(0, 2).map((n) => n.toFixed(2)).join(" · ")
            : technical.macd_assessment,
          "down",
        ),
      ],
      rows: [
        ["Trend", technical.trend],
        ["RSI", technical.rsi_assessment],
        ["MACD", technical.macd_assessment],
        ["Volume", technical.volume_assessment],
      ],
      lists: [
        {
          label: "Support",
          items: technical.support_levels.map((n) => n.toFixed(2)),
          tone: "up",
          numeric: true,
        },
        {
          label: "Resistance",
          items: technical.resistance_levels.map((n) => n.toFixed(2)),
          tone: "down",
          numeric: true,
        },
      ],
    },
    {
      key: "sentiment",
      label: "Sentiment",
      Icon: Newspaper,
      signal: sentiment.signal,
      confidence: sentiment.confidence,
      summary: sentiment.summary,
      evidence: [
        evidence("Tone", sentiment.news_tone, "neutral"),
        evidence("Theme", sentiment.key_themes[0] ?? sentiment.news_summary, "neutral"),
      ],
      rows: [
        ["News tone", sentiment.news_tone],
        ["News summary", sentiment.news_summary],
        ["Social sentiment", sentiment.social_sentiment ?? "—"],
      ],
      lists: [
        { label: "Key themes", items: sentiment.key_themes },
        { label: "Notable headlines", items: sentiment.notable_headlines },
      ],
    },
    {
      key: "macro",
      label: "Macro · FX",
      Icon: Globe,
      signal: macro.signal,
      confidence: macro.confidence,
      summary: macro.summary,
      evidence: [
        evidence("Sector factor", macro.sector_macro_factors[0] ?? macro.fed_impact, "up"),
        evidence("Risk", macro.geopolitical_risks[0] ?? macro.interest_rate_outlook, "down"),
      ],
      rows: [
        ["Fed impact", macro.fed_impact],
        ["Rates outlook", macro.interest_rate_outlook],
        ["FX impact", macro.fx_impact ?? "—"],
      ],
      lists: [
        { label: "Sector macro factors", items: macro.sector_macro_factors, tone: "up" },
        { label: "Geopolitical risks", items: macro.geopolitical_risks, tone: "down" },
      ],
    },
  ];
}

function evidence(label: string, text: string, tone: EvidenceTone): Evidence {
  return { label, text: clampText(text || "Not reported", 150), tone };
}

function DeskMatrix({ desks }: { desks: DeskDefinition[] }) {
  return (
    <div>
      <h3 className="eyebrow mb-3">Signal matrix</h3>

      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        {desks.map((desk) => (
          <article key={desk.key} className="rounded-lg border bg-card p-4">
            <header className="flex items-start justify-between gap-3">
              <h3 className="flex items-center gap-2 text-sm font-semibold text-ink">
                <desk.Icon className="size-4 text-graphite" aria-hidden />
                <span>{desk.label}</span>
              </h3>
              <SignalBadge signal={desk.signal} confidence={desk.confidence} size="lg" />
            </header>

            <SignalTrack signal={desk.signal} label={desk.label} />

            <p className="prose-claim mt-4 line-clamp-3 text-sm">{desk.summary}</p>

            <ul className="mt-4 space-y-2 border-t pt-3">
              {desk.evidence.map((item) => (
                <li key={item.label} className="flex gap-2 text-xs">
                  <span
                    className={cn(
                      "mt-0.5 shrink-0 font-medium",
                      item.tone === "up"
                        ? "text-bull"
                        : item.tone === "down"
                          ? "text-bear"
                          : "text-graphite",
                    )}
                    aria-hidden
                  >
                    {item.tone === "up" ? "▲" : item.tone === "down" ? "▼" : "•"}
                  </span>
                  <span className="min-w-0">
                    <span className="font-medium text-graphite">{item.label}: </span>
                    <span className="text-ink">{item.text}</span>
                  </span>
                </li>
              ))}
            </ul>
          </article>
        ))}
      </div>
    </div>
  );
}

function SignalTrack({ signal, label }: { signal: Signal; label: string }) {
  const position = signalPosition(signal);
  const left = ((position + 1) / 2) * 100;

  return (
    <div
      className="mt-4"
      role="img"
      aria-label={`${label} signal ${signalLabel(signal)} on a sell to buy axis`}
    >
      <div className="relative h-3">
        <div
          className="absolute left-0 right-0 top-1/2 h-1 -translate-y-1/2 rounded-full bg-gradient-to-r from-bear/60 via-graphite/20 to-bull/60"
          aria-hidden
        />
        <span
          className="absolute top-1/2 size-3 -translate-x-1/2 -translate-y-1/2 rounded-full bg-ink ring-2 ring-card"
          style={{ left: `${left}%` }}
          aria-hidden
        />
      </div>
      <div className="mt-1 flex justify-between text-mini uppercase tracking-[0.06em] text-graphite">
        <span>Sell</span>
        <span>Neutral</span>
        <span>Buy</span>
      </div>
    </div>
  );
}

function DeskNotes({ desks }: { desks: DeskDefinition[] }) {
  return (
    <div className="mt-7">
      <h3 className="eyebrow mb-2">Full desk notes</h3>
      <div className="border-y">
        {desks.map((desk) => (
          <details key={desk.key} className="group border-b last:border-b-0">
            <summary className="flex cursor-pointer list-none items-center justify-between gap-3 py-3">
              <span className="flex min-w-0 items-center gap-2">
                <desk.Icon className="size-3.5 shrink-0 text-graphite" aria-hidden />
                <span className="text-sm font-medium text-ink">{desk.label}</span>
                <span className="min-w-0 truncate text-micro text-graphite">
                  {desk.rows.map(([k]) => k).join(" · ")}
                </span>
              </span>
              <ChevronDown
                className="size-3.5 shrink-0 text-graphite transition-transform group-open:rotate-180"
                aria-hidden
              />
            </summary>
            <div className="pb-5 pt-1">
              <ReportView rows={desk.rows} lists={desk.lists} />
            </div>
          </details>
        ))}
      </div>
    </div>
  );
}

function ReportView({
  rows,
  lists,
}: {
  rows: Array<[string, string]>;
  lists: ListSpec[];
}) {
  return (
    <div className="space-y-5">
      {rows.length > 0 && (
        <dl className="grid gap-x-6 gap-y-4 border-t pt-4 sm:grid-cols-2">
          {rows.map(([k, v]) => (
            <div key={k} className="min-w-0">
              <dt className="eyebrow">{k}</dt>
              <dd className="prose-claim mt-1 text-sm text-graphite">{v || "—"}</dd>
            </div>
          ))}
        </dl>
      )}

      <div className="grid gap-5 border-t pt-4 md:grid-cols-2">
        {lists.map((list) => (
          <ItemList key={list.label} {...list} />
        ))}
      </div>
    </div>
  );
}

function ItemList({ label, items, tone, numeric }: ListSpec) {
  const marker =
    tone === "up" ? "bg-bull" : tone === "down" ? "bg-bear" : "bg-graphite";
  const glyphTone = tone === "up" ? "text-bull" : "text-bear";
  const glyph = tone === "up" ? "▲" : tone === "down" ? "▼" : null;

  return (
    <div>
      <h4 className="eyebrow mb-2 flex items-center gap-1.5">
        {glyph && (
          <span aria-hidden className={cn("text-mini tracking-normal", glyphTone)}>
            {glyph}
          </span>
        )}
        {label}
      </h4>
      {items && items.length > 0 ? (
        <ul className="space-y-1.5">
          {items.map((it, i) => (
            <li key={i} className="flex gap-2.5">
              <span
                className={cn("mt-2 inline-block size-1 shrink-0 rounded-full", marker)}
                aria-hidden
              />
              <span
                className={cn(
                  numeric ? "num text-sm text-ink" : "prose-claim text-sm",
                  !numeric && "max-w-[68ch]",
                )}
              >
                {it}
              </span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-sm text-graphite">None reported</p>
      )}
    </div>
  );
}
