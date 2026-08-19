export interface WatchlistEntry {
  /** Storage symbol — matches the directory name under data/. */
  symbol: string;
  market: "US" | "MY";
  theme: string | null;
}
