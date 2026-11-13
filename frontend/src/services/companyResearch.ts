export type CompanyMatch = { symbol: string; exchange: "NSE" | "BSE"; name: string };
export type CompanySearch = { status: "available" | "unavailable"; matches: CompanyMatch[]; note: string };
export type CompanySnapshot = {
  status: "available" | "unavailable"; symbol: string; exchange: string; name: string | null;
  provider: string; retrieved_at: string; expires_at: string | null; cached: boolean;
  source_url: string; screener_url: string; sector: string | null; industry: string | null;
  currency: string | null; price: string | null; price_as_of: string | null;
  metrics: { label: string; value: string | null; unit: string; period: string }[];
  statements: { title: string; currency: string; periods: string[]; rows: { label: string; unit: "currency" | "per_share"; values: (string | null)[] }[] }[];
  notes: string[];
};

export function screenerTicker(value: string): { symbol: string; exchange: "NSE" | "BSE" } | null {
  if (!/^https?:\/\//i.test(value)) return null;
  const url = new URL(value);
  if (url.protocol !== "https:" || !["www.screener.in", "screener.in"].includes(url.hostname) || url.username || url.password || url.port) {
    throw new Error("Paste an HTTPS company link from screener.in.");
  }
  const match = /^\/company\/([A-Za-z0-9&._-]{1,32})\/(?:consolidated\/)?$/.exec(url.pathname);
  if (!match) throw new Error("Use a Screener company link, for example https://www.screener.in/company/AARTIIND/consolidated/.");
  return { symbol: match[1].toUpperCase(), exchange: /^\d{6}$/.test(match[1]) ? "BSE" : "NSE" };
}

export function formatCompanyNumber(value: string | null, unit: string) {
  if (value === null || value === "" || !Number.isFinite(Number(value))) return "Unavailable";
  const amount = Number(value);
  const formatted = new Intl.NumberFormat("en-IN", { maximumFractionDigits: 2 }).format(unit === "INR" ? amount / 10000000 : amount);
  return unit === "INR" ? `₹ ${formatted} Cr` : unit === "%" ? `${formatted}%` : unit === "times" ? `${formatted}×` : unit === "INR / share" ? `₹ ${formatted}` : formatted;
}
