/** Where a ticker sits in the watchlist: something you own vs something you watch. */
export type WatchGroup = "holding" | "candidate";

export interface WatchlistEntry {
  /** Storage symbol — matches the directory name under data/. */
  symbol: string;
  market: "US" | "MY";
  group: WatchGroup;
  theme: string | null;
}
