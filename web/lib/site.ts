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
 * Revalidate window for upstream `fetch()` calls (Supabase REST, FastAPI).
 *
 * Next's fetch Data Cache is persisted to `.next/cache/fetch-cache/` on disk and
 * survives `next dev` restarts — a cached entry from days ago can outlive the
 * process that created it. That is the right trade in a real deployment (fewer
 * upstream reads under traffic), but on a local dev server it reads as "my data
 * is stuck" with no visible cause. Zero disables caching entirely in dev so
 * localhost always reflects the current DB state; production keeps the 60s ISR
 * window.
 */
export const FETCH_REVALIDATE_SECONDS =
  process.env.NODE_ENV === "development" ? 0 : 60;

/**
 * Tags where a visit came from, so a QR scan is distinguishable from a pasted
 * link in whatever analytics eventually lands here. Kept off the URL a human
 * reads — the tracking parameter is for the machine, not the reader.
 */
export function withSource(url: string, source: string): string {
  return `${url}${url.includes("?") ? "&" : "?"}s=${encodeURIComponent(source)}`;
}
