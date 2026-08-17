import type { CSSProperties } from "react";
import { DIRECTION_LABEL, TONE_EYEBROW } from "@/lib/conviction";
import { clampText, fmtCurrency, fmtDate, fmtSignedPercent } from "@/lib/format";
import type { TickerBundle } from "@/lib/types";
import { withSource } from "@/lib/site";
import { arrowDataUri, qrDataUri, sparklineDataUri } from "./assets";
import { buildCardSummary } from "./summary";
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

/**
 * 1080×1350 (4:5) rather than a phone-story 9:16 — the card's rows already
 * assume 1080px of width (the verdict/levels split, the sparkline), and a
 * narrower frame would force a second rewrite of every measurement in here.
 * 4:5 is also what Instagram and X actually keep uncropped in a feed, which is
 * the point of a "portrait" option in the first place.
 */
export const SHARE_CARD_SIZE_PORTRAIT = { width: 1080, height: 1350 } as const;

export type CardOrientation = "landscape" | "portrait";

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
  eyebrowStyle,
  portrait,
}: {
  label: string;
  value: number | null;
  currency: string;
  colour: string;
  eyebrowStyle: CSSProperties;
  portrait: boolean;
}) {
  return (
    <div style={{ display: "flex", flexDirection: "column" }}>
      <div style={eyebrowStyle}>{label}</div>
      <div
        style={{
          ...mono,
          display: "flex",
          marginTop: 8,
          fontSize: portrait ? 36 : 27,
          color: colour,
        }}
      >
        {fmtCurrency(value, currency)}
      </div>
    </div>
  );
}

export function ShareCard({
  bundle,
  url,
  orientation = "landscape",
}: {
  bundle: TickerBundle;
  url: string;
  orientation?: CardOrientation;
}) {
  const portrait = orientation === "portrait";
  const { currency, latestPrice, changePct, conviction, plan, hasLevels, thesis, asOf } =
    buildCardSummary(bundle);
  const info = bundle.fundamentals?.info;
  const up = (changePct ?? 0) >= 0;
  const briefing = bundle.briefing;

  // Portrait has ~2x the height of landscape at ~0.9x the width — filling
  // that with the same type scale reads as a landscape card floating in a
  // tall empty frame. Every size below scales off this one knob instead of
  // each spot inventing its own portrait number.
  const eyebrowStyle: CSSProperties = { ...eyebrow, fontSize: portrait ? 16 : 13 };

  // 180 sessions is roughly the page chart's 6M default — enough to show the
  // shape of a trend without compressing it into a straight line.
  const window = bundle.priceHistory.slice(-180);
  // Beside the verdict it shares the row on landscape; portrait stacks the
  // verdict above it, so the sparkline always runs the frame's full measure.
  const sparkWidth = portrait ? 960 : briefing ? 604 : 1080;
  // Portrait has roughly double the vertical room per unit of width, so the
  // sparkline gets to be an actual chart instead of the landscape hairline.
  const sparkHeight = portrait ? 160 : 70;
  const sparkline = sparklineDataUri(window, {
    width: sparkWidth,
    height: sparkHeight,
    up: (window.at(-1)?.close ?? 0) >= (window[0]?.close ?? 0),
  });

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        width: "100%",
        height: "100%",
        padding: portrait ? "56px 60px" : "44px 60px",
        backgroundColor: shareTheme.paper,
        color: shareTheme.ink,
        fontFamily: shareFonts.label,
        fontWeight: 500,
      }}
    >
      {/* Provenance, small and first: this is a multi-agent briefing, not a quote. */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div style={eyebrowStyle}>Desk · Multi-agent briefing</div>
        {asOf && <div style={eyebrowStyle}>As of {fmtDate(asOf)}</div>}
      </div>

      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "flex-start",
          marginTop: portrait ? 34 : 26,
        }}
      >
        <div style={{ display: "flex", flexDirection: "column", maxWidth: 660 }}>
          <div
            style={{
              display: "flex",
              fontFamily: shareFonts.display,
              fontWeight: 600,
              fontSize: portrait ? 88 : 64,
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
              fontSize: portrait ? 28 : 22,
              color: shareTheme.graphite,
              overflow: "hidden",
              whiteSpace: "nowrap",
              textOverflow: "ellipsis",
            }}
          >
            {info?.name ?? bundle.symbol}
          </div>
          {(info?.sector || info?.market) && (
            <div style={{ ...eyebrowStyle, marginTop: 12, letterSpacing: "0.07em" }}>
              {[info?.market, info?.sector].filter(Boolean).join(" · ")}
            </div>
          )}
        </div>

        <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end" }}>
          <div style={eyebrowStyle}>Last close</div>
          <div style={{ ...mono, display: "flex", marginTop: 8, fontSize: portrait ? 62 : 46 }}>
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
                fontSize: portrait ? 20 : 17,
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

      <div
        style={{
          display: "flex",
          height: 1,
          marginTop: portrait ? 30 : 22,
          backgroundColor: shareTheme.rule,
        }}
      />

      {conviction ? (
        <div
          style={{
            display: "flex",
            flexDirection: portrait ? "column" : "row",
            marginTop: portrait ? 36 : 24,
          }}
        >
          <div style={{ display: "flex", flexDirection: "column", width: portrait ? "100%" : 392 }}>
            <div style={eyebrowStyle}>{TONE_EYEBROW[conviction.tone]}</div>
            <div
              style={{
                display: "flex",
                marginTop: 6,
                fontFamily: shareFonts.display,
                fontWeight: 600,
                fontSize: portrait ? 108 : 84,
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
                  fontSize: portrait ? 23 : 18,
                  color: shareTheme.graphite,
                }}
              >
                {conviction.agreement.agreeing} of {conviction.agreement.total} desks back it
              </div>
            )}
          </div>

          <div
            style={{
              display: "flex",
              flexDirection: "column",
              // `flex: 1` grows along the main axis — fine in landscape's row
              // (the card's width is definite), but in portrait's column the
              // container's height is auto, so flex-grow has nothing to grow
              // against: Yoga collapses this box to zero height and every
              // child inside paints on top of the next sibling instead of
              // pushing it down.
              flex: portrait ? "none" : 1,
              marginTop: portrait ? 32 : 0,
            }}
          >
            {hasLevels ? (
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <Level
                  label="Entry"
                  value={plan!.entry_limit}
                  currency={currency}
                  colour={shareTheme.ink}
                  eyebrowStyle={eyebrowStyle}
                  portrait={portrait}
                />
                <Level
                  label="Stop"
                  value={plan!.stop_loss}
                  currency={currency}
                  colour={shareTheme.bear}
                  eyebrowStyle={eyebrowStyle}
                  portrait={portrait}
                />
                <Level
                  label="Target"
                  value={plan!.take_profit_1}
                  currency={currency}
                  colour={shareTheme.bull}
                  eyebrowStyle={eyebrowStyle}
                  portrait={portrait}
                />
              </div>
            ) : (
              // Withheld levels are a pipeline decision, not missing data, and
              // the card says so rather than leaving three blanks.
              <div style={{ display: "flex", flexDirection: "column" }}>
                <div style={eyebrowStyle}>No levels</div>
                <div
                  style={{
                    display: "flex",
                    marginTop: 8,
                    fontSize: portrait ? 26 : 20,
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
                height={sparkHeight}
                alt=""
                style={{ marginTop: portrait ? 28 : 18 }}
              />
            )}
          </div>
        </div>
      ) : (
        <div style={{ display: "flex", marginTop: 28, flexDirection: "column" }}>
          <div style={eyebrowStyle}>Layer 1 only</div>
          <div style={{ display: "flex", marginTop: 8, fontSize: portrait ? 32 : 26 }}>
            Price and fundamentals fetched — the desks have not run yet
          </div>
          {sparkline && (
            <img
              src={sparkline}
              width={sparkWidth}
              height={sparkHeight}
              alt=""
              style={{ marginTop: 20 }}
            />
          )}
        </div>
      )}

      {thesis && (
        <div
          style={{
            display: "flex",
            marginTop: portrait ? 40 : 22,
            // Clearance for the footer rule: at two lines the `marginTop: auto`
            // below collapses, and without this the rule cuts the descenders.
            marginBottom: 26,
            fontFamily: shareFonts.prose,
            fontWeight: 400,
            fontSize: portrait ? 32 : 22,
            lineHeight: 1.35,
            color: shareTheme.ink,
          }}
        >
          {/* Two lines at this measure. Longer and it crowds the footer; the
              card is a pointer to the briefing, not a substitute for it.
              Portrait's extra width-per-line and vertical room buys a third
              line rather than forcing the same two-line cut. */}
          {clampText(thesis, portrait ? 260 : 190)}
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
            <img
              src={qrDataUri(withSource(url, "qr"))}
              width={portrait ? 128 : 98}
              height={portrait ? 128 : 98}
              alt=""
            />
          </div>
          <div style={{ display: "flex", flexDirection: "column", marginLeft: 18 }}>
            <div style={{ display: "flex", fontSize: portrait ? 21 : 17 }}>
              {briefing ? "Scan for the full briefing" : "Scan for the live page"}
            </div>
            <div
              style={{
                ...mono,
                display: "flex",
                marginTop: 7,
                fontSize: portrait ? 18 : 15,
                color: shareTheme.graphite,
              }}
            >
              {url.replace(/^https?:\/\//, "")}
            </div>
          </div>
        </div>

        <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end" }}>
          <div style={eyebrowStyle}>Research, not investment advice</div>
          <div
            style={{
              display: "flex",
              marginTop: 8,
              fontSize: portrait ? 18 : 15,
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
