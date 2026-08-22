import { ImageResponse } from "next/og";
import { NextRequest } from "next/server";
import { loadTicker } from "@/lib/data";
import {
  SHARE_CARD_SIZE,
  SHARE_CARD_SIZE_PORTRAIT,
  ShareCard,
  type CardOrientation,
} from "@/lib/share/card";
import { loadShareFonts } from "@/lib/share/fonts";
import { SHARE_PREVIEW_CACHE_CONTROL } from "@/lib/share/cache";
import { tickerUrl } from "@/lib/site";

/**
 * On-demand render for the share dialog's preview — same `ShareCard` as
 * `opengraph-image.tsx`, but a plain route rather than a metadata image so it
 * can take an `?orientation=` query and isn't pinned to the OG protocol's one
 * picture per page. Always reads the current bundle off disk; there is no
 * `generateStaticParams` here on purpose, because the dialog is asking "what
 * does this look like right now", not warming a build artifact.
 */
export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ ticker: string }> },
) {
  const { ticker } = await params;
  const orientation: CardOrientation =
    request.nextUrl.searchParams.get("orientation") === "portrait" ? "portrait" : "landscape";

  const [bundle, fonts] = await Promise.all([loadTicker(ticker), loadShareFonts()]);
  if (!bundle) {
    return new Response("Not found", {
      status: 404,
      headers: { "Cache-Control": SHARE_PREVIEW_CACHE_CONTROL },
    });
  }

  const size = orientation === "portrait" ? SHARE_CARD_SIZE_PORTRAIT : SHARE_CARD_SIZE;

  return new ImageResponse(
    <ShareCard bundle={bundle} url={tickerUrl(bundle.symbol)} orientation={orientation} />,
    {
      ...size,
      fonts,
      headers: { "Cache-Control": SHARE_PREVIEW_CACHE_CONTROL },
    },
  );
}
