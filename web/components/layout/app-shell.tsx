"use client";

import { useEffect, useState } from "react";
import { usePathname } from "next/navigation";
import { Sidebar } from "./sidebar";
import { Topbar } from "./topbar";
import { cn } from "@/lib/utils";
import type { TickerNavSummary } from "@/lib/types";

export function AppShell({
  tickers,
  children,
}: {
  tickers: TickerNavSummary[];
  children: React.ReactNode;
}) {
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const pathname = usePathname();

  useEffect(() => {
    setMobileNavOpen(false);
  }, [pathname]);

  useEffect(() => {
    if (!mobileNavOpen) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setMobileNavOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [mobileNavOpen]);

  return (
    <div className="flex min-h-dvh">
      {/* A real button, not a click-catching div: the scrim is the only way to
          dismiss the drawer by pointer, so it has to be reachable and named. */}
      <button
        type="button"
        onClick={() => setMobileNavOpen(false)}
        aria-label="Close navigation menu"
        tabIndex={mobileNavOpen ? 0 : -1}
        aria-hidden={!mobileNavOpen}
        className={cn(
          "fixed inset-0 z-40 bg-ink/40 backdrop-blur-sm transition-opacity lg:hidden",
          mobileNavOpen ? "opacity-100" : "pointer-events-none opacity-0",
        )}
      />

      <Sidebar
        tickers={tickers}
        open={mobileNavOpen}
        onClose={() => setMobileNavOpen(false)}
      />

      <div className="flex min-w-0 flex-1 flex-col">
        <Topbar onMenuClick={() => setMobileNavOpen(true)} tickers={tickers} />
        <main id="main" className="flex-1">
          <div className="mx-auto w-full max-w-shell px-5 py-8 md:px-10 md:py-10">
            {children}
          </div>
        </main>
        <footer className="border-t px-5 py-6 text-xs text-graphite md:px-10">
          <div className="mx-auto flex max-w-shell flex-wrap items-center justify-between gap-2">
            <span>Desk · Multi-Agent Research</span>
            <span>Not investment advice — for research only</span>
          </div>
        </footer>
      </div>
    </div>
  );
}
