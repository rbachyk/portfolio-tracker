// Centralised formatting helpers. Every number rendered in the dashboard goes
// through one of these so the ledger reads consistently and uses tabular figures.

export const QUOTE_ASSET = "USDT";

// Product name. Mirrors the backend APP_NAME setting; override at build time
// with VITE_APP_NAME. Kept here so the brand reads from one place.
export const APP_NAME = (import.meta.env.VITE_APP_NAME as string | undefined) || "Crypto Portfolio Tracker";

// Stablecoins treated as "cash" for the allocation breakdown. The dashboard
// shows portfolio distribution both including and excluding these.
export const CASH_ASSETS = new Set(["USDT", "USDC", "FDUSD", "BUSD", "DAI", "TUSD", "USDP"]);

type Numish = string | number | null | undefined;

export function toNumber(value: Numish): number | null {
  if (value === null || value === undefined || value === "") return null;
  const numeric = typeof value === "number" ? value : Number(value);
  return Number.isFinite(numeric) ? numeric : null;
}

/** Grouped decimal, e.g. 128440.2 -> "128,440.20". Returns em dash when empty. */
export function fmtNum(value: Numish, fractionDigits = 2): string {
  const numeric = toNumber(value);
  if (numeric === null) return "—";
  return numeric.toLocaleString(undefined, {
    minimumFractionDigits: fractionDigits,
    maximumFractionDigits: fractionDigits,
  });
}

/** Money in the quote asset. `signed` prefixes an explicit + for positives. */
export function fmtMoney(value: Numish, options: { signed?: boolean } = {}): string {
  const numeric = toNumber(value);
  if (numeric === null) return "—";
  const sign = options.signed && numeric > 0 ? "+" : "";
  return `${sign}${fmtNum(numeric, 2)}`;
}

/** Token quantity — up to 8 decimals, trailing zeros trimmed. */
export function fmtQty(value: Numish): string {
  const numeric = toNumber(value);
  if (numeric === null) return "—";
  return numeric.toLocaleString(undefined, { maximumFractionDigits: 8 });
}

/** Adaptive price: more precision for sub-dollar assets, less for large ones. */
export function fmtPrice(value: Numish): string {
  const numeric = toNumber(value);
  if (numeric === null) return "—";
  const abs = Math.abs(numeric);
  let digits = 2;
  if (abs !== 0 && abs < 1) digits = 6;
  if (abs !== 0 && abs < 0.01) digits = 8;
  return numeric.toLocaleString(undefined, { maximumFractionDigits: digits });
}

/** Fraction (0–1) to percent string. `signed` adds + for gains. */
export function fmtPct(value: Numish, options: { signed?: boolean } = {}): string {
  const numeric = toNumber(value);
  if (numeric === null) return "—";
  const pct = numeric * 100;
  const sign = options.signed && pct > 0 ? "+" : "";
  return `${sign}${pct.toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}%`;
}

/** Compact axis/label form: 1.2K, 3.4M, 980. */
export function fmtCompact(value: Numish): string {
  const numeric = toNumber(value);
  if (numeric === null) return "—";
  return numeric.toLocaleString(undefined, {
    notation: "compact",
    maximumFractionDigits: 2,
  });
}

export type Sign = "pos" | "neg" | "flat";

export function signOf(value: Numish): Sign {
  const numeric = toNumber(value) ?? 0;
  if (numeric > 0) return "pos";
  if (numeric < 0) return "neg";
  return "flat";
}

export function fmtDateTime(value: string | null | undefined): string {
  if (!value) return "Never";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Never";
  return date.toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function fmtDate(value: string | null | undefined): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return date.toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "2-digit",
  });
}

/** "just now", "4m ago", "3h ago", "2d ago" — for last-sync indicators. */
export function relativeTime(value: string | null | undefined, now: number = Date.now()): string {
  if (!value) return "never";
  const date = new Date(value);
  const ms = now - date.getTime();
  if (Number.isNaN(ms)) return "never";
  if (ms < 0) return "just now";
  const seconds = Math.floor(ms / 1000);
  if (seconds < 45) return "just now";
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 30) return `${days}d ago`;
  return fmtDate(value);
}

export function shortId(value: string | null | undefined): string {
  if (!value) return "—";
  if (value.length <= 14) return value;
  return `${value.slice(0, 6)}…${value.slice(-6)}`;
}

export function titleCase(value: string): string {
  return value
    .replaceAll("_", " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
}
