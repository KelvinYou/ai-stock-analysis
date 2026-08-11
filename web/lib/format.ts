export function fmtNumber(n: number | null | undefined, digits = 2): string {
  if (n == null || !Number.isFinite(n)) return "—";
  return n.toLocaleString("en-US", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

export function fmtCurrency(n: number | null | undefined, currency = "USD"): string {
  if (n == null || !Number.isFinite(n)) return "—";
  return n.toLocaleString("en-US", {
    style: "currency",
    currency,
    maximumFractionDigits: 2,
  });
}

export function fmtCompact(n: number | null | undefined, currency?: string): string {
  if (n == null || !Number.isFinite(n)) return "—";
  const opts: Intl.NumberFormatOptions = {
    notation: "compact",
    maximumFractionDigits: 2,
  };
  if (currency) {
    opts.style = "currency";
    opts.currency = currency;
  }
  return n.toLocaleString("en-US", opts);
}

export function fmtPercent(n: number | null | undefined, digits = 2, fromDecimal = false): string {
  if (n == null || !Number.isFinite(n)) return "—";
  const v = fromDecimal ? n * 100 : n;
  return `${v >= 0 ? "+" : ""}${v.toFixed(digits)}%`;
}

export function fmtSignedPercent(n: number | null | undefined, digits = 2): string {
  if (n == null || !Number.isFinite(n)) return "—";
  return `${n >= 0 ? "+" : ""}${n.toFixed(digits)}%`;
}

/**
 * Pull a sortable number out of a risk/reward string.
 * "1.33:1" → 1.33 · "0.78:1" → 0.78 · "N/A (bearish signal)" → null.
 */
export function parseRatio(s: string | null | undefined): number | null {
  if (!s) return null;
  const m = /^\s*(\d+(?:\.\d+)?)\s*:\s*(\d+(?:\.\d+)?)/.exec(s);
  if (!m) return null;
  const denominator = Number(m[2]);
  if (!denominator) return null;
  return Number(m[1]) / denominator;
}

/** "0.9% of portfolio" → "0.9%". Falls back to the raw string. */
export function shortPositionSize(s: string | null | undefined): string {
  if (!s) return "—";
  return /(\d+(?:\.\d+)?\s*%)/.exec(s)?.[1].replace(/\s+/g, "") ?? s;
}

/** "4d" / "today". Compact enough for a table cell. */
export function fmtAge(days: number | null | undefined): string {
  if (days == null) return "—";
  if (days === 0) return "today";
  return `${days}d`;
}

export function signalLabel(s: string | null | undefined): string {
  if (!s) return "—";
  return s.replace("_", " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

export function fmtDate(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.valueOf())) return iso;
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}

export function fmtDateShort(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.valueOf())) return iso;
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}
