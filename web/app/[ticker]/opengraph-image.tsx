import { ImageResponse } from "next/og";
import { listTickers, loadTicker } from "@/lib/data";
import { SHARE_CARD_SIZE, ShareCard } from "@/lib/share/card";
import { loadShareFonts } from "@/lib/share/fonts";
import { SHARE_METADATA_CACHE_CONTROL } from "@/lib/share/cache";
import { shareFonts, shareTheme } from "@/lib/share/theme";
import { tickerUrl } from "@/lib/site";

/**
 * The share card, as this route's Open Graph image.
 *
 * Deliberately a metadata route rather than an `/api/...` handler: the button in
 * the header and the preview that unfurls when someone pastes the link into
 * Slack or WhatsApp then render from the same source, so they can never
 * disagree.
 *
 * No `runtime = "edge"` here, on purpose — the card reads the briefing through
 * the server-side data adapter, which may use Node's local fallback.
 */
export const alt = "Multi-agent briefing summary";
export const size = SHARE_CARD_SIZE;
export const contentType = "image/png";
export const revalidate = 60;
export const dynamicParams = true;

/**
 * A metadata image route does *not* inherit the params its page enumerates —
 * without this the route builds as dynamic and every card is rendered on the
 * first request that asks for it, scraper included. Repeating it here puts each
 * card in the build output beside its page, on the same revalidation clock.
 */
export async function generateStaticParams() {
  const tickers = await listTickers();
  return tickers.map((ticker) => ({ ticker }));
}

export default async function Image({
  params,
}: {
  params: Promise<{ ticker: string }>;
}) {
  const { ticker } = await params;
  const [bundle, fonts] = await Promise.all([loadTicker(ticker), loadShareFonts()]);

  if (!bundle) {
    // The page itself 404s in this case; the image only has to not crash the
    // build, so it degrades to the wordmark rather than throwing.
    return new ImageResponse(
      (
        <div
          style={{
            display: "flex",
            width: "100%",
            height: "100%",
            alignItems: "center",
            justifyContent: "center",
            backgroundColor: shareTheme.paper,
            color: shareTheme.ink,
            fontFamily: shareFonts.display,
            fontWeight: 600,
            fontSize: 64,
            letterSpacing: "-0.03em",
          }}
        >
          Desk
        </div>
      ),
      {
        ...size,
        fonts,
        headers: { "Cache-Control": SHARE_METADATA_CACHE_CONTROL },
      },
    );
  }

  return new ImageResponse(
    <ShareCard bundle={bundle} url={tickerUrl(bundle.symbol)} />,
    {
      ...size,
      fonts,
      headers: { "Cache-Control": SHARE_METADATA_CACHE_CONTROL },
    },
  );
}
