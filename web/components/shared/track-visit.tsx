"use client";

import { useEffect } from "react";
import { addRecentlyViewed } from "@/lib/client-storage";

export function TrackVisit({ symbol }: { symbol: string }) {
  useEffect(() => {
    addRecentlyViewed(symbol);
    window.dispatchEvent(new CustomEvent("recent-change"));
  }, [symbol]);

  return null;
}
