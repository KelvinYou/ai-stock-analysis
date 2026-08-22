import type { NextConfig } from "next";
import { SHARE_METADATA_CACHE_CONTROL } from "./lib/share/cache";

const config: NextConfig = {
  typedRoutes: false,

  /**
   * The metadata image routes are prerendered, and Next stamps its own
   * `immutable, max-age=31536000` onto every prerendered response. That is safe
   * only when the URL busts on change — but Next derives the `?<hash>` on a
   * metadata image URL from the route, not the rendered bytes, so every ticker
   * shares one hash that never moves while the briefing underneath it does.
   * Without this override a scraper pins the day-one card for a year.
   */
  async headers() {
    return [
      {
        source: "/:ticker/:image(opengraph-image|twitter-image)",
        headers: [
          { key: "Cache-Control", value: SHARE_METADATA_CACHE_CONTROL },
        ],
      },
    ];
  },
};

export default config;
