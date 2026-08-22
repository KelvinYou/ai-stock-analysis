/** The preview is user-facing and should always reflect the current bundle. */
export const SHARE_PREVIEW_CACHE_CONTROL = "private, no-store";

/** Metadata images may be reused briefly, but must not be pinned for a year. */
export const SHARE_METADATA_CACHE_CONTROL =
  "public, max-age=0, s-maxage=60, stale-while-revalidate=300";
