import {
  DIRECTION_LABEL,
  TONE_EYEBROW,
  describeConviction,
} from "@/lib/conviction";
import { clampText, fmtCurrency, fmtDate, fmtSignedPercent } from "@/lib/format";
import type { TickerBundle } from "@/lib/types";
import { withSource } from "@/lib/site";
import { arrowDataUri, qrDataUri, sparklineDataUri } from "./assets";
import { shareFonts, shareTheme } from "./theme";

/**
 * The share card: one image that has to answer "what does this ticker say?" at
 * a glance, in a timeline, at thumbnail size.
 *
 * Written as inline styles rather than Tailwind because Satori resolves no
 * stylesheet, no class, and no CSS variable. The constraints worth remembering
 * while editing this file:
 *
 *   - flexbox only — no grid, no `calc()`, no `z-index`
 *   - `display: flex` must be set explicitly on every container
 *   - no line clamping; long prose is cut in JS below
 *   - anything that is not a box or a glyph arrives as a data-URI `<img>`
 *
 * 1200×675 is 16:9 and clears Open Graph's 600×315 floor. X crops a large
 * summary card toward 1.91:1, which eats roughly 24px off the top and bottom —
 * hence the generous vertical padding, which is a safe zone rather than taste.
 */
export const SHARE_CARD_SIZE = { width: 1200, height: 675 } as const;

const VERDICT_COLOUR = {
  bull: shareTheme.bull,
  bear: shareTheme.bear,
  // Hold stays ink, exactly as on the page: a neutral verdict is a result.
  neutral: shareTheme.ink,
} as const;

const eyebrow = {
  display: "flex",
  fontFamily: shareFonts.display,
  fontWeight: 600,
  fontSize: 13,
  letterSpacing: "0.09em",
  textTransform: "uppercase",
  color: shareTheme.graphite,
} as const;

const mono = {
  fontFamily: shareFonts.mono,
  fontWeight: 400,
  letterSpacing: "-0.02em",
} as const;

function Level({
  label,
  value,
  currency,
  colour,
}: {
  label: string;
  value: number | null;
  currency: string;
  colour: string;
}) {
  return (
    <div style={{ display: "flex", flexDirection: "column" }}>
      <div style={eyebrow}>{label}</div>
      <div style={{ ...mono, display: "flex", marginTop: 8, fontSize: 27, color: colour }}>
        {fmtCurrency(value, currency)}
      </div>
    </div>
  );
}

export function ShareCard({ bundle, url }: { bundle: TickerBundle; url: string }) {
  const info = bundle.fundamentals?.info;
  const currency = info?.currency ?? "USD";

  const latestPrice = bundle.priceHistory.at(-1)?.close ?? bundle.technicals?.close ?? null;
  const prevPrice = bundle.priceHistory.at(-2)?.close ?? null;
  const changePct =
    latestPrice != null && prevPrice != null && prevPrice !== 0
      ? ((latestPrice - prevPrice) / prevPrice) * 100
      : null;
  const up = (changePct ?? 0) >= 0;

  const briefing = bundle.briefing;
  const conviction = briefing ? describeConviction(briefing) : null;
  const plan = briefing?.action_plan ?? null;
  const hasLevels =
    !!plan &&
    (plan.entry_limit !== null || plan.stop_loss !== null || plan.take_profit_1 !== null);

  // The verdict's own prose, in order of authority: the adjudicator's thesis if
  // the research manager ran, otherwise the synthesis summary.
  const thesis = briefing
    ? (briefing.research_verdict?.thesis ?? briefing.executive_summary ?? "")
    : "";

  // 180 sessions is roughly the page chart's 6M default — enough to show the
  // shape of a trend without compressing it into a straight line.
  const window = bundle.priceHistory.slice(-180);
  // Beside the verdict it shares the row; without one it is the only exhibit
  // there is, and runs the full measure.
  const sparkWidth = briefing ? 604 : 1080;
  const sparkline = sparklineDataUri(window, {
    width: sparkWidth,
    height: 70,
    up: (window.at(-1)?.close ?? 0) >= (window[0]?.close ?? 0),
  });

  const asOf = briefing?.date ?? bundle.technicals?.as_of_date ?? bundle.priceHistory.at(-1)?.date;

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        width: "100%",
        height: "100%",
        padding: "44px 60px",
        backgroundColor: shareTheme.paper,
        color: shareTheme.ink,
        fontFamily: shareFonts.label,
        fontWeight: 500,
      }}
    >
      {/* Provenance, small and first: this is a multi-agent briefing, not a quote. */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div style={eyebrow}>Desk · Multi-agent briefing</div>
        {asOf && <div style={eyebrow}>As of {fmtDate(asOf)}</div>}
      </div>

      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "flex-start",
          marginTop: 26,
        }}
      >
        <div style={{ display: "flex", flexDirection: "column", maxWidth: 660 }}>
          <div
            style={{
              display: "flex",
              fontFamily: shareFonts.display,
              fontWeight: 600,
              fontSize: 64,
              lineHeight: 1,
              letterSpacing: "-0.03em",
            }}
          >
            {bundle.symbol}
          </div>
          <div
            style={{
              display: "flex",
              marginTop: 10,
              fontSize: 22,
              color: shareTheme.graphite,
              overflow: "hidden",
              whiteSpace: "nowrap",
              textOverflow: "ellipsis",
            }}
          >
            {info?.name ?? bundle.symbol}
          </div>
          {(info?.sector || info?.market) && (
            <div style={{ ...eyebrow, marginTop: 12, letterSpacing: "0.07em" }}>
              {[info?.market, info?.sector].filter(Boolean).join(" · ")}
            </div>
          )}
        </div>

        <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end" }}>
          <div style={eyebrow}>Last close</div>
          <div style={{ ...mono, display: "flex", marginTop: 8, fontSize: 46 }}>
            {fmtCurrency(latestPrice, currency)}
          </div>
          {changePct != null && (
            // Arrow, sign, and hue all say the same thing, so the direction
            // survives a greyscale repost or a colour-blind reader.
            <div
              style={{
                ...mono,
                display: "flex",
                alignItems: "center",
                marginTop: 9,
                fontSize: 17,
                color: shareTheme.graphite,
              }}
            >
              <img src={arrowDataUri(up)} width={11} height={9} alt="" />
              <span style={{ marginLeft: 7, color: up ? shareTheme.bull : shareTheme.bear }}>
                {fmtSignedPercent(changePct)}
              </span>
              <span style={{ marginLeft: 7 }}>vs previous</span>
            </div>
          )}
        </div>
      </div>

      <div style={{ display: "flex", height: 1, marginTop: 22, backgroundColor: shareTheme.rule }} />

      {conviction ? (
        <div style={{ display: "flex", marginTop: 24 }}>
          <div style={{ display: "flex", flexDirection: "column", width: 392 }}>
            <div style={eyebrow}>{TONE_EYEBROW[conviction.tone]}</div>
            <div
              style={{
                display: "flex",
                marginTop: 6,
                fontFamily: shareFonts.display,
                fontWeight: 600,
                fontSize: 84,
                lineHeight: 0.95,
                letterSpacing: "-0.03em",
                color: VERDICT_COLOUR[conviction.agreement.direction],
              }}
            >
              {DIRECTION_LABEL[conviction.agreement.direction]}
            </div>
            {conviction.agreement.total > 0 && (
              <div
                style={{
                  display: "flex",
                  marginTop: 12,
                  fontSize: 18,
                  color: shareTheme.graphite,
                }}
              >
                {conviction.agreement.agreeing} of {conviction.agreement.total} desks back it
              </div>
            )}
          </div>

          <div style={{ display: "flex", flexDirection: "column", flex: 1 }}>
            {hasLevels ? (
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <Level
                  label="Entry"
                  value={plan!.entry_limit}
                  currency={currency}
                  colour={shareTheme.ink}
                />
                <Level
                  label="Stop"
                  value={plan!.stop_loss}
                  currency={currency}
                  colour={shareTheme.bear}
                />
                <Level
                  label="Target"
                  value={plan!.take_profit_1}
                  currency={currency}
                  colour={shareTheme.bull}
                />
              </div>
            ) : (
              // Withheld levels are a pipeline decision, not missing data, and
              // the card says so rather than leaving three blanks.
              <div style={{ display: "flex", flexDirection: "column" }}>
                <div style={eyebrow}>No levels</div>
                <div
                  style={{
                    display: "flex",
                    marginTop: 8,
                    fontSize: 20,
                    color: shareTheme.halt,
                  }}
                >
                  Convergence too low to quote a setup
                </div>
              </div>
            )}

            {sparkline && (
              <img
                src={sparkline}
                width={sparkWidth}
                height={70}
                alt=""
                style={{ marginTop: 18 }}
              />
            )}
          </div>
        </div>
      ) : (
        <div style={{ display: "flex", marginTop: 28, flexDirection: "column" }}>
          <div style={eyebrow}>Layer 1 only</div>
          <div style={{ display: "flex", marginTop: 8, fontSize: 26 }}>
            Price and fundamentals fetched — the desks have not run yet
          </div>
          {sparkline && (
            <img src={sparkline} width={sparkWidth} height={70} alt="" style={{ marginTop: 20 }} />
          )}
        </div>
      )}

      {thesis && (
        <div
          style={{
            display: "flex",
            marginTop: 22,
            // Clearance for the footer rule: at two lines the `marginTop: auto`
            // below collapses, and without this the rule cuts the descenders.
            marginBottom: 26,
            fontFamily: shareFonts.prose,
            fontWeight: 400,
            fontSize: 22,
            lineHeight: 1.35,
            color: shareTheme.ink,
          }}
        >
          {/* Two lines at this measure. Longer and it crowds the footer; the
              card is a pointer to the briefing, not a substitute for it. */}
          {clampText(thesis, 190)}
        </div>
      )}

      <div
        style={{
          display: "flex",
          marginTop: "auto",
          paddingTop: 20,
          borderTop: `1px solid ${shareTheme.rule}`,
          justifyContent: "space-between",
          alignItems: "flex-end",
        }}
      >
        <div style={{ display: "flex", alignItems: "center" }}>
          {/* White plate under the code: a QR on the paper grey still scans, but
              only just, and a shared image gets photographed off screens. */}
          <div
            style={{
              display: "flex",
              padding: 6,
              backgroundColor: shareTheme.surface,
              borderRadius: 4,
            }}
          >
            <img src={qrDataUri(withSource(url, "qr"))} width={98} height={98} alt="" />
          </div>
          <div style={{ display: "flex", flexDirection: "column", marginLeft: 18 }}>
            <div style={{ display: "flex", fontSize: 17 }}>
              {briefing ? "Scan for the full briefing" : "Scan for the live page"}
            </div>
            <div
              style={{
                ...mono,
                display: "flex",
                marginTop: 7,
                fontSize: 15,
                color: shareTheme.graphite,
              }}
            >
              {url.replace(/^https?:\/\//, "")}
            </div>
          </div>
        </div>

        <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end" }}>
          <div style={eyebrow}>Research, not investment advice</div>
          <div
            style={{
              display: "flex",
              marginTop: 8,
              fontSize: 15,
              color: shareTheme.graphite,
            }}
          >
            Four analyst desks · adversarial debate · synthesis
          </div>
        </div>
      </div>
    </div>
  );
}
