import type { Metadata } from "next";
import localFont from "next/font/local";
import { AppShell } from "@/components/layout/app-shell";
import { themeScript } from "@/components/shared/theme-toggle";
import { listTickerNavSummaries } from "@/lib/data";
import { SITE_URL } from "@/lib/site";
import "./globals.css";

// Three faces, three kinds of claim. Archivo (run wide) carries structure —
// headers, tickers, the verdict word. Newsreader carries argument: every string
// an LLM reasoned out. DM Mono carries anything the pipeline computed. Keeping
// them disjoint is what makes "argued vs. calculated" legible at a glance.
const display = localFont({
  src: "../assets/fonts/Archivo-Expanded-SemiBold.ttf",
  variable: "--font-display",
  display: "swap",
});

const prose = localFont({
  src: "../assets/fonts/Newsreader-Regular.ttf",
  variable: "--font-prose",
  display: "swap",
});

const mono = localFont({
  src: "../assets/fonts/DMMono-Regular.ttf",
  variable: "--font-mono",
  display: "swap",
});

export const metadata: Metadata = {
  // Required for the share cards: without it Next emits a relative `og:image`,
  // which every scraper ignores. Set NEXT_PUBLIC_SITE_URL per deployment.
  metadataBase: new URL(SITE_URL),
  title: "Desk · Stock Briefings",
  description:
    "Multi-agent briefings across fundamentals, technicals, sentiment, and macro.",
};

// The shell owns live ticker navigation, so it must share the same ISR window
// even on routes whose page content has no data fetch of its own.
export const revalidate = 60;

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const navTickers = await listTickerNavSummaries();
  return (
    <html
      lang="en"
      className={`${display.variable} ${prose.variable} ${mono.variable}`}
      suppressHydrationWarning
    >
      <body className="min-h-dvh bg-background font-display text-foreground antialiased">
        {/* Sets the theme class before first paint so the page never flashes
            the wrong ground. Must run inline, ahead of hydration. */}
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
        <a
          href="#main"
          className="sr-only focus:not-sr-only focus:fixed focus:left-3 focus:top-3 focus:z-50 focus:rounded-md focus:bg-foreground focus:px-3 focus:py-2 focus:text-background"
        >
          Skip to main content
        </a>
        <AppShell tickers={navTickers}>{children}</AppShell>
      </body>
    </html>
  );
}
