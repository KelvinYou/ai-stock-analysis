import { BarChart3, Globe, Newspaper, TrendingUp } from "lucide-react";
import { SectionCard } from "@/components/shared/section-card";
import { SignalBadge } from "./signal-badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import type { AnalystReports } from "@/lib/types";

const TABS = [
  { key: "fundamentals", label: "Fundamentals", Icon: BarChart3 },
  { key: "technical", label: "Technical", Icon: TrendingUp },
  { key: "sentiment", label: "Sentiment", Icon: Newspaper },
  { key: "macro", label: "Macro · FX", Icon: Globe },
] as const;

export function AnalystSection({ data }: { data: AnalystReports }) {
  return (
    <SectionCard
      id="analysts"
      chapter="03"
      title="Specialist Desks"
      description="Four analysts read the tape independently"
    >
      <Tabs defaultValue="fundamentals">
        <TabsList className="flex h-auto w-full flex-wrap items-stretch justify-start rounded-none bg-transparent p-0 border-b hairline">
          {TABS.map(({ key, label, Icon }, i) => (
            <TabsTrigger
              key={key}
              value={key}
              className="relative flex h-auto items-center gap-2 rounded-none border-b-2 border-transparent bg-transparent px-4 py-3 text-muted-foreground data-[state=active]:border-primary data-[state=active]:bg-transparent data-[state=active]:text-foreground data-[state=active]:shadow-none"
            >
              <span className="num hidden text-[10px] uppercase tracking-[0.22em] opacity-70 sm:inline">
                0{i + 1}
              </span>
              <Icon className="size-3.5" />
              <span className="text-[13px]">{label}</span>
            </TabsTrigger>
          ))}
        </TabsList>

        <TabsContent value="fundamentals" className="mt-6">
          <ReportView
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
              ["Key strengths", data.fundamentals.key_strengths, "up"],
              ["Key risks", data.fundamentals.key_risks, "down"],
            ]}
          />
        </TabsContent>

        <TabsContent value="technical" className="mt-6">
          <ReportView
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
              [
                "Support",
                data.technical.support_levels.map((n) => n.toFixed(2)),
                "up",
              ],
              [
                "Resistance",
                data.technical.resistance_levels.map((n) => n.toFixed(2)),
                "down",
              ],
            ]}
          />
        </TabsContent>

        <TabsContent value="sentiment" className="mt-6">
          <ReportView
            summary={data.sentiment.summary}
            signal={data.sentiment.signal}
            confidence={data.sentiment.confidence}
            rows={[
              ["News tone", data.sentiment.news_tone],
              ["News summary", data.sentiment.news_summary],
              ["Social sentiment", data.sentiment.social_sentiment ?? "—"],
            ]}
            lists={[
              ["Key themes", data.sentiment.key_themes],
              ["Notable headlines", data.sentiment.notable_headlines],
            ]}
          />
        </TabsContent>

        <TabsContent value="macro" className="mt-6">
          <ReportView
            summary={data.macro.summary}
            signal={data.macro.signal}
            confidence={data.macro.confidence}
            rows={[
              ["Fed impact", data.macro.fed_impact],
              ["Rates outlook", data.macro.interest_rate_outlook],
              ["FX impact", data.macro.fx_impact ?? "—"],
            ]}
            lists={[
              ["Sector macro factors", data.macro.sector_macro_factors, "up"],
              ["Geopolitical risks", data.macro.geopolitical_risks, "down"],
            ]}
          />
        </TabsContent>
      </Tabs>
    </SectionCard>
  );
}

function ReportView({
  summary,
  signal,
  confidence,
  rows,
  lists,
}: {
  summary: string;
  signal: AnalystReports["fundamentals"]["signal"];
  confidence: AnalystReports["fundamentals"]["confidence"];
  rows: Array<[string, string]>;
  lists: Array<[string, string[], ("up" | "down")?]>;
}) {
  return (
    <div className="space-y-6 animate-fade-in">
      <div className="flex flex-wrap items-center gap-3">
        <SignalBadge signal={signal} confidence={confidence} size="lg" />
      </div>

      <p className="display text-base leading-relaxed text-foreground/95 md:text-[17px]">
        {summary}
      </p>

      <div className="grid gap-px overflow-hidden rounded-sm border hairline bg-border/40 md:grid-cols-2">
        {rows.map(([k, v]) => (
          <div key={k} className="bg-background/80 p-4">
            <div className="text-[10px] uppercase tracking-[0.22em] text-muted-foreground/80">
              {k}
            </div>
            <p className="mt-1.5 text-sm leading-relaxed text-foreground/95">{v || "—"}</p>
          </div>
        ))}
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        {lists.map(([k, items, tone]) => {
          const marker =
            tone === "up"
              ? "text-emerald-400"
              : tone === "down"
                ? "text-rose-400"
                : "text-primary/70";
          return (
            <div key={k}>
              <h4 className="mb-3 text-[10px] uppercase tracking-[0.22em] text-muted-foreground/80">
                {k}
              </h4>
              {items && items.length > 0 ? (
                <ul className="space-y-2 text-sm">
                  {items.map((it, i) => (
                    <li key={i} className="flex gap-3">
                      <span className={`num mt-0.5 text-[10px] ${marker}`}>
                        {String(i + 1).padStart(2, "0")}
                      </span>
                      <span className="leading-relaxed text-foreground/95">{it}</span>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-sm italic text-muted-foreground/70">None reported</p>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
