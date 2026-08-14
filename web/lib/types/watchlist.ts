/** Where a ticker sits in the public watchlist: actively tracked vs candidate. */
export type WatchGroup = "tracked" | "candidate";

export interface WatchlistEntry {
  /** Storage symbol — matches the directory name under data/. */
  symbol: string;
  market: "US" | "MY";
  group: WatchGroup;
  theme: string | null;
}
