import type { Signal } from "@/lib/types";

/**
 * How a signal is drawn outside the consensus axis.
 *
 * Chroma is reserved for `components/consensus/`, so everywhere else a signal
 * has to be carried by shape and words instead of hue. The glyph doubles up
 * (▲▲ / ▼▼) for the strong readings so magnitude survives without a second
 * colour stop, and the label is always rendered alongside it — the glyph is
 * decoration, the label is the value.
 *
 * Shared because the screener, the sidebar and the topbar search each used to
 * keep their own copy of a coloured-dot map, and the three drifted apart.
 */

const GLYPH: Record<Signal, string> = {
  strong_buy: "▲▲",
  buy: "▲",
  neutral: "●",
  sell: "▼",
  strong_sell: "▼▼",
};

const SHORT_LABEL: Record<Signal, string> = {
  strong_buy: "Strong buy",
  buy: "Buy",
  neutral: "Neutral",
  sell: "Sell",
  strong_sell: "Strong sell",
};

/** Direction mark for a signal. Decorative — pair it with `signalShortLabel`. */
export function signalGlyph(signal: Signal | null | undefined): string {
  return signal ? GLYPH[signal] : "·";
}

/** Table-width name for a signal. "Not briefed" when the pipeline hasn't run. */
export function signalShortLabel(signal: Signal | null | undefined): string {
  return signal ? SHORT_LABEL[signal] : "Not briefed";
}
