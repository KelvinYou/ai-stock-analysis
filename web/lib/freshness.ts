/**
 * Whether a stored briefing still describes the current price data.
 *
 * Mirror of `stock_analysis/synthesis/freshness.py`, which is the canonical
 * owner of this rule. It exists twice because two of the three read paths go
 * through Python (the FastAPI adapter computes and sends `briefing_stale`) but
 * the direct-Supabase path in `data.ts` derives its summary rows in the
 * browser tier and has no Python to ask. Keep the two in step: the thresholds
 * and the branch order below are the contract.
 *
 * The failure this catches: `stock-fetch` refreshes prices daily while the LLM
 * layers only rerun with the full pipeline, so a `buy` adjudicated on a
 * $592.85 close sat beside a $617.79 tape for a week and read as current.
 * Plain age does not catch it — a five-day-old briefing is fine if the stock
 * did not move, and misleading if it ran 8%.
 */

/** Beyond this, a briefing is old news even with no newer bar to compare to. */
export const STALE_AFTER_DAYS = 7;

export interface Freshness {
  stale: boolean;
  reason: string | null;
}

const FRESH: Freshness = { stale: false, reason: null };

function toUtcDay(iso: string | null | undefined): number | null {
  if (!iso) return null;
  const parsed = Date.parse(`${iso.slice(0, 10)}T00:00:00Z`);
  return Number.isNaN(parsed) ? null : parsed;
}

const DAY_MS = 86_400_000;

/**
 * @param briefingDate  When the run happened.
 * @param dataAsOf      Newest price bar the run actually read. Preferred over
 *                      `briefingDate`; absent on briefings written before the
 *                      field existed, in which case the run date stands in
 *                      (it is the same day or later, so the check stays
 *                      conservative).
 * @param latestBarDate Newest bar available now.
 */
export function assessFreshness(
  briefingDate: string | null | undefined,
  dataAsOf: string | null | undefined,
  latestBarDate: string | null | undefined,
): Freshness {
  const referenceIso = dataAsOf ?? briefingDate ?? null;
  const reference = toUtcDay(referenceIso);
  if (reference == null) {
    return { stale: true, reason: "Briefing has no date; treat as unverified." };
  }

  const latest = toUtcDay(latestBarDate);
  if (latest != null && latest > reference) {
    const lag = Math.round((latest - reference) / DAY_MS);
    return {
      stale: true,
      reason:
        `Briefing analysed price data through ${referenceIso!.slice(0, 10)}; ` +
        `bars now run to ${latestBarDate!.slice(0, 10)} (${lag}d newer). ` +
        "Its signal, conviction and levels predate the current tape — " +
        "rerun the pipeline before acting.",
    };
  }

  const now = new Date();
  const today = Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate());
  const age = Math.round((today - reference) / DAY_MS);
  if (age > STALE_AFTER_DAYS) {
    return {
      stale: true,
      reason:
        `Briefing analysed price data through ${referenceIso!.slice(0, 10)}, ` +
        `${age} days ago (limit ${STALE_AFTER_DAYS}d). ` +
        "Rerun the pipeline before acting.",
    };
  }

  return FRESH;
}
