/**
 * The origin this deployment answers on. It has to be absolute and it has to be
 * correct: it is what the share card's QR code encodes, and a QR pointing at
 * `localhost` is a dead scan on someone else's phone.
 *
 * Set `NEXT_PUBLIC_SITE_URL` in the environment for any deployment that is not
 * the local dev server.
 */
export const SITE_URL = (
  process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000"
).replace(/\/+$/, "");

/** The origin without its scheme — what a human reads next to a QR code. */
export const SITE_HOST = SITE_URL.replace(/^https?:\/\//, "");

/** The canonical, shareable address of a ticker's page. */
export function tickerUrl(symbol: string): string {
  return `${SITE_URL}/${encodeURIComponent(symbol)}`;
}

/**
 * Tags where a visit came from, so a QR scan is distinguishable from a pasted
 * link in whatever analytics eventually lands here. Kept off the URL a human
 * reads — the tracking parameter is for the machine, not the reader.
 */
export function withSource(url: string, source: string): string {
  return `${url}${url.includes("?") ? "&" : "?"}s=${encodeURIComponent(source)}`;
}
