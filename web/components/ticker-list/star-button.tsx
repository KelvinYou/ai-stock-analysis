"use client";

import { useState, useEffect } from "react";
import { Star } from "lucide-react";
import { getMyList, toggleMyList } from "@/lib/client-storage";
import { cn } from "@/lib/utils";

export function StarButton({ symbol, className }: { symbol: string; className?: string }) {
  const [starred, setStarred] = useState(false);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
    setStarred(getMyList().includes(symbol));
  }, [symbol]);

  if (!mounted) return <span className="size-6" aria-hidden />;

  function toggle(e: React.MouseEvent) {
    e.preventDefault();
    e.stopPropagation();
    const next = toggleMyList(symbol);
    setStarred(next.includes(symbol));
    window.dispatchEvent(new CustomEvent("mylist-change"));
  }

  return (
    <button
      type="button"
      onClick={toggle}
      aria-label={starred ? `Unstar ${symbol}` : `Star ${symbol}`}
      className={cn(
        "rounded p-1 transition-colors",
        starred
          ? "text-amber-400 hover:text-amber-500"
          : "text-muted-foreground/30 hover:text-muted-foreground",
        className,
      )}
    >
      <Star className={cn("size-3.5", starred && "fill-current")} />
    </button>
  );
}
