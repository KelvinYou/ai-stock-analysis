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
      title="Specialist desks"
      description="Four analysts read the tape independently"
    >
      <Tabs defaultValue="fundamentals">
        <TabsList className="flex h-auto w-full flex-wrap items-stretch justify-start gap-1 rounded-lg bg-muted/40 p-1">
          {TABS.map(({ key, label, Icon }) => (
            <TabsTrigger
              key={key}
              value={key}
              className="flex h-auto items-center gap-1.5 rounded-md px-3 py-1.5 text-[13px] font-medium text-muted-foreground data-[state=active]:bg-background data-[state=active]:text-foreground data-[state=active]:shadow-sm"
            >
              <Icon className="size-3.5" />
              <span>{label}</span>
            </TabsTrigger>
          ))}
        </TabsList>

        <TabsContent value="fundamentals" className="mt-5">
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

        <TabsContent value="technical" className="mt-5">
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
              ["Support", data.technical.support_levels.map((n) => n.toFixed(2)), "up"],
              ["Resistance", data.technical.resistance_levels.map((n) => n.toFixed(2)), "down"],
            ]}
          />
        </TabsContent>

        <TabsContent value="sentiment" className="mt-5">
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

        <TabsContent value="macro" className="mt-5">
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
    <div className="space-y-5">
      <div className="flex flex-wrap items-center gap-3">
        <SignalBadge signal={signal} confidence={confidence} size="lg" />
      </div>

      <p className="text-[15px] leading-relaxed text-foreground">{summary}</p>

      <div className="grid gap-3 md:grid-cols-2">
        {rows.map(([k, v]) => (
          <div key={k} className="rounded-lg border bg-background p-4">
            <div className="text-[11px] font-medium text-muted-foreground">{k}</div>
            <p className="mt-1 text-sm leading-relaxed text-foreground">{v || "—"}</p>
          </div>
        ))}
      </div>

      <div className="grid gap-5 md:grid-cols-2">
        {lists.map(([k, items, tone]) => {
          const marker =
            tone === "up"
              ? "bg-emerald-500"
              : tone === "down"
                ? "bg-rose-500"
                : "bg-foreground/40";
          return (
            <div key={k}>
              <h4 className="mb-2 text-[11px] font-medium text-muted-foreground">{k}</h4>
              {items && items.length > 0 ? (
                <ul className="space-y-1.5 text-sm">
                  {items.map((it, i) => (
                    <li key={i} className="flex gap-2.5">
                      <span
                        className={`mt-1.5 inline-block size-1 shrink-0 rounded-full ${marker}`}
                      />
                      <span className="leading-relaxed text-foreground">{it}</span>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-sm text-muted-foreground">None reported</p>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
