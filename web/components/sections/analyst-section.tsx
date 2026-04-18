import { BarChart3, Globe, Newspaper, TrendingUp } from "lucide-react";
import { SectionCard } from "./section-card";
import { SignalBadge } from "@/components/signal-badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import type { AnalystReports } from "@/lib/types";

const TABS = [
  { key: "fundamentals", label: "Fundamentals", Icon: BarChart3 },
  { key: "technical", label: "Technical", Icon: TrendingUp },
  { key: "sentiment", label: "Sentiment", Icon: Newspaper },
  { key: "macro", label: "Macro / FX", Icon: Globe },
] as const;

export function AnalystSection({ data }: { data: AnalystReports }) {
  return (
    <SectionCard
      id="analysts"
      title="Analyst agents"
      description="Four specialist agents read the raw data independently"
    >
      <Tabs defaultValue="fundamentals">
        <TabsList className="flex w-full flex-wrap">
          {TABS.map(({ key, label, Icon }) => {
            const r = data[key as keyof AnalystReports];
            return (
              <TabsTrigger key={key} value={key} className="flex items-center gap-2">
                <Icon className="size-3.5" />
                <span>{label}</span>
                <span className="ml-1 hidden sm:inline">
                  <SignalBadge signal={r.signal} size="sm" />
                </span>
              </TabsTrigger>
            );
          })}
        </TabsList>

        <TabsContent value="fundamentals">
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

        <TabsContent value="technical">
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

        <TabsContent value="sentiment">
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

        <TabsContent value="macro">
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
    <div className="space-y-5 animate-fade-in">
      <div className="flex flex-wrap items-center gap-3">
        <SignalBadge signal={signal} confidence={confidence} size="lg" />
      </div>
      <p className="text-sm leading-relaxed text-foreground/90">{summary}</p>

      <div className="grid gap-4 md:grid-cols-2">
        {rows.map(([k, v]) => (
          <div key={k} className="rounded-lg border border-border/50 bg-muted/20 p-4">
            <div className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
              {k}
            </div>
            <p className="mt-1.5 text-sm leading-relaxed">{v || "—"}</p>
          </div>
        ))}
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        {lists.map(([k, items, tone]) => (
          <div key={k}>
            <h4 className="mb-2 text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
              {k}
            </h4>
            {items && items.length > 0 ? (
              <ul className="space-y-1.5 text-sm">
                {items.map((it, i) => (
                  <li key={i} className="flex gap-2">
                    <span
                      className={
                        tone === "up"
                          ? "text-emerald-400"
                          : tone === "down"
                            ? "text-rose-400"
                            : "text-muted-foreground"
                      }
                    >
                      •
                    </span>
                    <span className="leading-relaxed">{it}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-muted-foreground">None reported</p>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
