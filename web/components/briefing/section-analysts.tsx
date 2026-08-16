import { BarChart3, Globe, Newspaper, TrendingUp } from "lucide-react";
import { SectionCard } from "@/components/shared/section-card";
import { SignalBadge } from "./signal-badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { cn } from "@/lib/utils";
import type { AnalystReports } from "@/lib/types";

const TABS = [
  { key: "fundamentals", label: "Fundamentals", Icon: BarChart3 },
  { key: "technical", label: "Technical", Icon: TrendingUp },
  { key: "sentiment", label: "Sentiment", Icon: Newspaper },
  { key: "macro", label: "Macro · FX", Icon: Globe },
] as const;

/** A named list under a report. `numeric` items are computed, so they set in mono. */
type ListSpec = {
  label: string;
  items: string[];
  tone?: "up" | "down";
  numeric?: boolean;
};

export function AnalystSection({ data }: { data: AnalystReports }) {
  return (
    <SectionCard
      id="analysts"
      tier="argument"
      layer="Layer 2 · Four desks"
      title="Specialist desks"
      description="Four analysts read the tape independently"
    >
      <Tabs defaultValue="fundamentals">
        <TabsList>
          {TABS.map(({ key, label, Icon }) => (
            <TabsTrigger key={key} value={key}>
              <Icon className="size-3.5" aria-hidden />
              <span>{label}</span>
            </TabsTrigger>
          ))}
        </TabsList>

        <TabsContent value="fundamentals">
          <ReportView
            desk="Fundamentals"
            summary={data.fundamentals.summary}
            signal={data.fundamentals.signal}
            confidence={data.fundamentals.confidence}
            rows={[
              ["P/E assessment", data.fundamentals.pe_assessment],
              ["Margin analysis", data.fundamentals.margin_analysis],
              ["Debt analysis", data.fundamentals.debt_analysis],
              ["Growth outlook", data.fundamentals.growth_outlook],
            ]}
            lists={[
              { label: "Key strengths", items: data.fundamentals.key_strengths, tone: "up" },
              { label: "Key risks", items: data.fundamentals.key_risks, tone: "down" },
            ]}
          />
        </TabsContent>

        <TabsContent value="technical">
          <ReportView
            desk="Technical"
            summary={data.technical.summary}
            signal={data.technical.signal}
            confidence={data.technical.confidence}
            rows={[
              ["Trend", data.technical.trend],
              ["RSI", data.technical.rsi_assessment],
              ["MACD", data.technical.macd_assessment],
              ["Volume", data.technical.volume_assessment],
            ]}
            lists={[
              {
                label: "Support",
                items: data.technical.support_levels.map((n) => n.toFixed(2)),
                tone: "up",
                numeric: true,
              },
              {
                label: "Resistance",
                items: data.technical.resistance_levels.map((n) => n.toFixed(2)),
                tone: "down",
                numeric: true,
              },
            ]}
          />
        </TabsContent>

        <TabsContent value="sentiment">
          <ReportView
            desk="Sentiment"
            summary={data.sentiment.summary}
            signal={data.sentiment.signal}
            confidence={data.sentiment.confidence}
            rows={[
              ["News tone", data.sentiment.news_tone],
              ["News summary", data.sentiment.news_summary],
              ["Social sentiment", data.sentiment.social_sentiment ?? "—"],
            ]}
            lists={[
              { label: "Key themes", items: data.sentiment.key_themes },
              { label: "Notable headlines", items: data.sentiment.notable_headlines },
            ]}
          />
        </TabsContent>

        <TabsContent value="macro">
          <ReportView
            desk="Macro · FX"
            summary={data.macro.summary}
            signal={data.macro.signal}
            confidence={data.macro.confidence}
            rows={[
              ["Fed impact", data.macro.fed_impact],
              ["Rates outlook", data.macro.interest_rate_outlook],
              ["FX impact", data.macro.fx_impact ?? "—"],
            ]}
            lists={[
              {
                label: "Sector macro factors",
                items: data.macro.sector_macro_factors,
                tone: "up",
              },
              {
                label: "Geopolitical risks",
                items: data.macro.geopolitical_risks,
                tone: "down",
              },
            ]}
          />
        </TabsContent>
      </Tabs>
    </SectionCard>
  );
}

function ReportView({
  desk,
  summary,
  signal,
  confidence,
  rows,
  lists,
}: {
  desk: string;
  summary: string;
  signal: AnalystReports["fundamentals"]["signal"];
  confidence: AnalystReports["fundamentals"]["confidence"];
  rows: Array<[string, string]>;
  lists: ListSpec[];
}) {
  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b pb-3">
        <h3 className="text-sm font-semibold text-ink">{desk} desk</h3>
        <SignalBadge signal={signal} confidence={confidence} size="lg" />
      </div>

      <p className="prose-claim max-w-[68ch]">{summary}</p>

      <div className="grid gap-3 md:grid-cols-2">
        {rows.map(([k, v]) => (
          <div key={k} className="rounded-lg border bg-card p-4">
            <h4 className="eyebrow">{k}</h4>
            <p className="prose-claim mt-1.5 text-sm">{v || "—"}</p>
          </div>
        ))}
      </div>

      <div className="grid gap-5 md:grid-cols-2">
        {lists.map((list) => (
          <ItemList key={list.label} {...list} />
        ))}
      </div>
    </div>
  );
}

function ItemList({ label, items, tone, numeric }: ListSpec) {
  // Direction lands on the glyph and the bullet, never on the label: "Key
  // risks" already says which side this is, and an untoned list still reads.
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
