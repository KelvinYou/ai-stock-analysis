import type { Metadata } from "next";
import { Instrument_Sans, IBM_Plex_Mono } from "next/font/google";
import { AppShell } from "@/components/layout/app-shell";
import { listTickerSummaries } from "@/lib/data";
import "./globals.css";

const sans = Instrument_Sans({
  subsets: ["latin"],
  variable: "--font-sans",
  display: "swap",
});

const mono = IBM_Plex_Mono({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-mono",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Desk · Stock Briefings",
  description:
    "Multi-agent briefings across fundamentals, technicals, sentiment, and macro.",
};

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const tickers = await listTickerSummaries();
  return (
    <html lang="en" className={`${sans.variable} ${mono.variable}`}>
      <body className="min-h-dvh bg-background font-sans text-foreground antialiased">
        <a
          href="#main"
          className="sr-only focus:not-sr-only focus:fixed focus:left-3 focus:top-3 focus:z-50 focus:rounded-md focus:bg-foreground focus:px-3 focus:py-2 focus:text-background"
        >
          Skip to main content
        </a>
        <AppShell tickers={tickers}>{children}</AppShell>
      </body>
    </html>
  );
}
