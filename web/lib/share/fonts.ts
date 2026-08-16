import { readFile } from "node:fs/promises";
import path from "node:path";
import { shareFonts } from "./theme";

/**
 * Satori accepts ttf/otf/woff only — never woff2, and nothing `next/font` hands
 * back — so the card's faces are committed to the repo as static, subsetted
 * TTFs. See `assets/fonts/README.md` for how they were produced.
 *
 * The read is memoised because it is the expensive part of rendering a card and
 * the bytes never depend on the request. Every ticker's image resolves the same
 * promise.
 */
const FONT_DIR = path.resolve(process.cwd(), "assets", "fonts");

type ShareFont = {
  name: string;
  data: ArrayBuffer;
  weight: 400 | 500 | 600;
  style: "normal";
};

let cached: Promise<ShareFont[]> | null = null;

async function load(file: string): Promise<ArrayBuffer> {
  const buf = await readFile(path.join(FONT_DIR, file));
  return buf.buffer.slice(
    buf.byteOffset,
    buf.byteOffset + buf.byteLength,
  ) as ArrayBuffer;
}

export function loadShareFonts(): Promise<ShareFont[]> {
  cached ??= (async () => {
    const [display, label, prose, mono] = await Promise.all([
      load("Archivo-Expanded-SemiBold.ttf"),
      load("Archivo-Medium.ttf"),
      load("Newsreader-Regular.ttf"),
      load("DMMono-Regular.ttf"),
    ]);

    // Each family is registered at exactly one weight, and every style in the
    // card names that same weight. Ask Satori for a weight it has no face for
    // and it synthesises one, which is how a card ends up faux-bold.
    return [
      { name: shareFonts.display, data: display, weight: 600, style: "normal" },
      { name: shareFonts.label, data: label, weight: 500, style: "normal" },
      { name: shareFonts.prose, data: prose, weight: 400, style: "normal" },
      { name: shareFonts.mono, data: mono, weight: 400, style: "normal" },
    ] satisfies ShareFont[];
  })();

  return cached;
}
