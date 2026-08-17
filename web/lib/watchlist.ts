import { promises as fs } from "node:fs";
import path from "node:path";
import { cache } from "react";
import type { WatchGroup, WatchlistEntry } from "./types/watchlist";

const WATCHLIST_FILE = process.env.STOCK_TICKERS_FILE
  ? path.resolve(process.env.STOCK_TICKERS_FILE)
  : path.resolve(process.cwd(), "..", "tickers.txt");
const SUPABASE_URL =
  process.env.SUPABASE_URL ?? process.env.NEXT_PUBLIC_SUPABASE_URL ?? "";
const SUPABASE_KEY =
  process.env.SUPABASE_PUBLISHABLE_KEY ??
  process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY ??
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ??
  "";

const GROUP_MARKER = /^#\s*group:\s*(tracked|candidate)s?\s*$/i;
const THEME_MARKER = /^#\s*theme:\s*(.+?)\s*$/i;

/**
 * Parse tickers.txt into structured entries.
 *
 * The file stays the single source of truth shared with fetch.py; grouping is
 * carried by `#group:` / `#theme:` comment markers, which fetch.py skips as
 * ordinary comments. `@universe` directives are ignored here — expanding them
 * needs a network fetch, and this watchlist deliberately lists tickers by hand.
 */
export function parseWatchlist(text: string): WatchlistEntry[] {
  const entries: WatchlistEntry[] = [];
  const seen = new Set<string>();
  let group: WatchGroup = "candidate";
  let theme: string | null = null;

  for (const raw of text.split(/\r?\n/)) {
    const line = raw.trim();
    if (!line) continue;
    if (line.startsWith("#")) {
      const g = GROUP_MARKER.exec(line);
      if (g) {
        group = g[1].toLowerCase() as WatchGroup;
        continue;
      }
      const t = THEME_MARKER.exec(line);
      if (t) theme = t[1];
      continue;
    }
    if (line.startsWith("@")) continue;

    const isMY = line.toUpperCase().startsWith("MY:");
    const symbol = (isMY ? line.slice(3) : line).trim().toUpperCase();
    if (!symbol || seen.has(symbol)) continue;
    seen.add(symbol);
    entries.push({ symbol, market: isMY ? "MY" : "US", group, theme });
  }
  return entries;
}

export const loadWatchlist = cache(async (): Promise<WatchlistEntry[]> => {
  if (SUPABASE_URL && SUPABASE_KEY) {
    const response = await fetch(
      `${SUPABASE_URL.replace(/\/$/, "")}/rest/v1/tickers?select=symbol,market,watch_group,theme&enabled=eq.true&order=symbol.asc`,
      {
        headers: {
          apikey: SUPABASE_KEY,
          Authorization: `Bearer ${SUPABASE_KEY}`,
        },
        next: { revalidate: 60 },
      },
    );
    if (!response.ok) {
      throw new Error(`Supabase watchlist failed (${response.status})`);
    }
    const rows = (await response.json()) as Array<{
      symbol: string;
      market: "US" | "MY";
      watch_group: WatchGroup | null;
      theme: string | null;
    }>;
    return rows.map((row) => ({
      symbol: row.symbol,
      market: row.market,
      group: row.watch_group ?? "candidate",
      theme: row.theme,
    }));
  }
  try {
    return parseWatchlist(await fs.readFile(WATCHLIST_FILE, "utf8"));
  } catch {
    return [];
  }
});

export const loadWatchlistMap = cache(
  async (): Promise<Record<string, WatchlistEntry>> =>
    Object.fromEntries((await loadWatchlist()).map((e) => [e.symbol, e])),
);
