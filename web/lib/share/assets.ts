import "server-only";

import { renderSVG } from "uqr";
import type { PricePoint } from "@/lib/types";
import { shareTheme } from "./theme";

/**
 * Everything Satori draws that is not a box or a glyph has to arrive as an
 * `<img>`, and the safest source for one is a base64 data URI.
 *
 * Base64 rather than `data:image/svg+xml;utf8,...` on purpose: Satori fails to
 * parse an un-encoded SVG data URI containing commas (vercel/satori#597), and
 * both a QR matrix and a sparkline are nothing but comma-separated path data.
 */
function svgDataUri(svg: string): string {
  return `data:image/svg+xml;base64,${Buffer.from(svg).toString("base64")}`;
}

/**
 * A QR code for `url`.
 *
 * `ecc: "M"` (15% recovery) is the standard trade-off for a screen code — `L`
 * gives a smaller matrix but leaves nothing in hand for a phone reading a
 * photograph of a screen, which is the actual path most of these take. The
 * 4-module border is the quiet zone the spec requires; without it, scanners
 * that find the code flush against other artwork simply fail to lock on.
 */
export function qrDataUri(url: string): string {
  return svgDataUri(
    renderSVG(url, {
      ecc: "M",
      border: 4,
      blackColor: shareTheme.ink,
      whiteColor: shareTheme.surface,
    }),
  );
}

/**
 * The price series as a standalone SVG.
 *
 * Recharts cannot run here — Satori renders static JSX with no layout engine
 * behind it and no DOM to measure — so the line is projected by hand. That is
 * a feature at this size: a share card wants the shape of the move, not axes,
 * gridlines, or a tooltip.
 */
export function sparklineDataUri(
  history: PricePoint[],
  { width, height, up }: { width: number; height: number; up: boolean },
): string | null {
  const closes = history.map((p) => p.close).filter(Number.isFinite);
  if (closes.length < 2) return null;

  const min = Math.min(...closes);
  const max = Math.max(...closes);
  const span = max - min || 1;

  // Inset by the stroke's half-width top and bottom, or the extremes clip.
  const stroke = 3;
  const top = stroke / 2;
  const usable = height - stroke;

  const points = closes.map((close, i) => {
    const x = (i / (closes.length - 1)) * width;
    const y = top + (1 - (close - min) / span) * usable;
    return `${x.toFixed(2)},${y.toFixed(2)}`;
  });

  const line = `M${points.join("L")}`;
  const area = `${line}L${width},${height}L0,${height}Z`;
  const colour = up ? shareTheme.bull : shareTheme.bear;

  // Same rule as the page's chart: the series carries direction in colour, but
  // the signed number above it says so in words, so hue is never the only cue.
  return svgDataUri(
    `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}">` +
      `<path d="${area}" fill="${colour}" fill-opacity="0.10"/>` +
      `<path d="${line}" fill="none" stroke="${colour}" stroke-width="${stroke}" ` +
      `stroke-linejoin="round" stroke-linecap="round"/>` +
      `</svg>`,
  );
}

/**
 * The ▲/▼ that sits beside the day's change, drawn rather than typeset — the
 * subsetted card fonts carry Latin and punctuation only, and a missing glyph in
 * Satori is a silent blank rather than a visible error.
 */
export function arrowDataUri(up: boolean): string {
  const colour = up ? shareTheme.bull : shareTheme.bear;
  const path = up ? "M6 0L12 10H0Z" : "M6 10L0 0H12Z";
  return svgDataUri(
    `<svg xmlns="http://www.w3.org/2000/svg" width="12" height="10" viewBox="0 0 12 10">` +
      `<path d="${path}" fill="${colour}"/></svg>`,
  );
}
