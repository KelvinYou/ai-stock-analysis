/**
 * X reads `twitter:image` in preference to `og:image`, and crops a
 * `summary_large_image` toward 1.91:1. The card is built with that crop in mind
 * (see the vertical safe zone in `lib/share/card.tsx`), so the same image
 * serves both — this file exists only to emit the second meta tag.
 */
export {
  default,
  alt,
  size,
  contentType,
  generateStaticParams,
} from "./opengraph-image";

// Restated rather than re-exported: Next reads `revalidate` by static analysis
// and silently falls back to the default when it arrives through a re-export.
// Keep this equal to the value in `opengraph-image.tsx`.
export const revalidate = 60;
