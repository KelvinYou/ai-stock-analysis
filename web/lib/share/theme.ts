/**
 * The palette, as literal colour values, for anything that renders outside the
 * browser.
 *
 * Satori (the engine behind `next/og`) never sees `globals.css`: there is no
 * cascade, no `hsl(var(--bull))`, no Tailwind class. The share card therefore
 * needs concrete colours — and a second, hand-written copy of the palette is
 * precisely how a design system drifts apart.
 *
 * The compromise: copy the *triplets* verbatim out of `app/globals.css :root`
 * and derive the hex here. A triplet is greppable, so `159 59% 30%` appearing
 * in two files is a diff either side will surface; a hex would not be.
 *
 * Only the light ground is mirrored. A shared image has no viewer to ask about
 * theme preference, and a card that arrives dark in a light timeline reads as a
 * screenshot of somebody else's screen rather than as a document.
 */

/** Verbatim from `app/globals.css` `:root`. Keep the two in sync. */
const LIGHT_HSL = {
  paper: "220 13% 95%",
  surface: "0 0% 100%",
  ink: "225 17% 9%",
  graphite: "217 6% 41%",
  rule: "220 10% 89%",
  bull: "159 59% 30%",
  bear: "2 59% 45%",
  halt: "42 63% 33%",
  action: "223 65% 48%",
} as const;

/**
 * `"220 13% 95%"` → `"#eff0f2"`. Mirrors what the browser does with
 * `hsl(var(--paper))`, which is the only reason the two grounds match.
 */
function hslToHex(triplet: string): string {
  const [h, s, l] = triplet
    .split(/\s+/)
    .map((part) => Number.parseFloat(part.replace("%", "")));

  const sat = s / 100;
  const lig = l / 100;
  const chroma = (1 - Math.abs(2 * lig - 1)) * sat;
  const secondary = chroma * (1 - Math.abs(((h / 60) % 2) - 1));
  const match = lig - chroma / 2;

  const sector = Math.floor(h / 60) % 6;
  const [r, g, b] = (
    [
      [chroma, secondary, 0],
      [secondary, chroma, 0],
      [0, chroma, secondary],
      [0, secondary, chroma],
      [secondary, 0, chroma],
      [chroma, 0, secondary],
    ] as const
  )[sector];

  const channel = (v: number) =>
    Math.round((v + match) * 255)
      .toString(16)
      .padStart(2, "0");

  return `#${channel(r)}${channel(g)}${channel(b)}`;
}

export const shareTheme = {
  paper: hslToHex(LIGHT_HSL.paper),
  surface: hslToHex(LIGHT_HSL.surface),
  ink: hslToHex(LIGHT_HSL.ink),
  graphite: hslToHex(LIGHT_HSL.graphite),
  rule: hslToHex(LIGHT_HSL.rule),
  bull: hslToHex(LIGHT_HSL.bull),
  bear: hslToHex(LIGHT_HSL.bear),
  halt: hslToHex(LIGHT_HSL.halt),
  action: hslToHex(LIGHT_HSL.action),
} as const;

/**
 * Three faces, three kinds of claim — the same split `app/layout.tsx` sets up.
 * `Archivo Expanded` is a static instance pinned at `wdth=125`, because the
 * `[font-stretch:125%]` the page uses is a variable-font axis and Satori
 * renders variable fonts at their default instance. See `assets/fonts/README.md`.
 */
export const shareFonts = {
  display: "Archivo Expanded",
  label: "Archivo",
  prose: "Newsreader",
  mono: "DM Mono",
} as const;
