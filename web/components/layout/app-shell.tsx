"use client";

import { useEffect, useState } from "react";
import { usePathname } from "next/navigation";
import { Sidebar } from "./sidebar";
import { Topbar } from "./topbar";
import { cn } from "@/lib/utils";
import type { TickerSummary } from "@/lib/types";

export function AppShell({
  tickers,
  children,
}: {
  tickers: TickerSummary[];
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
    <div className="relative z-10 flex min-h-dvh">
      <div
        onClick={() => setMobileNavOpen(false)}
        className={cn(
          "fixed inset-0 z-40 bg-black/70 backdrop-blur-sm transition-opacity lg:hidden",
          mobileNavOpen ? "opacity-100" : "pointer-events-none opacity-0",
        )}
        aria-hidden={!mobileNavOpen}
      />

      <Sidebar
        tickers={tickers}
        open={mobileNavOpen}
        onClose={() => setMobileNavOpen(false)}
      />

      <div className="flex min-w-0 flex-1 flex-col">
        <Topbar tickers={tickers} onMenuClick={() => setMobileNavOpen(true)} />
        <main id="main" className="flex-1">
          <div className="mx-auto w-full max-w-[1320px] px-5 py-8 md:px-10 md:py-12">
            {children}
          </div>
        </main>
        <footer className="border-t hairline px-5 py-5 text-[10px] uppercase tracking-[0.22em] text-muted-foreground/70 md:px-10">
          <div className="mx-auto flex max-w-[1320px] flex-wrap items-center justify-between gap-2">
            <span>The Desk · Multi-Agent Research</span>
            <span className="display italic tracking-normal text-muted-foreground/60">
              Not investment advice · for research &amp; backtest only
            </span>
          </div>
        </footer>
      </div>
    </div>
  );
}
