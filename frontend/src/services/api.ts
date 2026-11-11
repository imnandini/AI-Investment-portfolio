const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000").replace(/\/$/, "");

export type ApiError = Error & { status?: number; code?: string; retryAfter?: number };
export type VerificationResponse = { message: string; verification_required: boolean; resend_after_seconds: number };
export type HealthResponse = { status: string };

export type User = { id: string; email: string; email_verified: boolean; created_at: string };
export type TokenResponse = { access_token: string; token_type: string; expires_in: number };
export type Portfolio = { id: string; name: string; base_currency: string; created_at: string; updated_at: string };
export type Instrument = { id: string; canonical_symbol: string; display_name?: string | null; exchange: string; asset_type: string; currency: string; sector: string | null };
export type BalanceAsset = { symbol: string; display_name: string; asset_type: string; currency: string; invested_amount: string | null; market_value: string; as_of: string | null; imported_at: string };
export type Holding = { id: string; quantity: string; average_cost: string | null; source?: string; purchase_date: string | null; instrument: Instrument };
export type HoldingAnalytics = {
  symbol: string; exchange: string; asset_type: string; sector: string | null; currency: string;
  quantity: string; average_cost: string | null; cost_basis: string | null; current_price: string | null;
  market_value: string | null; unrealized_pl: string | null; market_allocation_pct: string | null;
  unrealized_return_pct: string | null;
  cost_basis_allocation_pct: string | null; price_as_of: string | null;
  price_status: "available" | "missing" | "currency_mismatch" | "stale" | "unknown_freshness";
  price_source?: string | null; price_kind?: "reference" | "daily_close" | null; price_exchange?: string | null;
};
export type PriceComparison = { label: string; from_date: string; to_date: string; previous_value: string; latest_value: string; change: string; change_pct: string | null };
export type DailyPriceOverview = { configured: boolean; provider: string; requested_through: string; latest_date: string | null; checked_at: string | null; covered_positions: number; position_count: number; notes: string[]; comparisons: PriceComparison[]; comparison_basis: string };
export type MixEntry = { name: string; cost_basis: string; allocation_pct: string | null };
export type PortfolioAnalytics = {
  portfolio_id: string; base_currency: string; methodology: string; cost_basis_total: string | null;
  market_value_total: string | null; unrealized_pl_total: string | null; largest_holding_symbol: string | null;
  unrealized_return_pct: string | null;
  largest_holding_allocation_pct: string | null; concentration_index: string | null; asset_mix: MixEntry[];
  sector_mix: MixEntry[]; positions: HoldingAnalytics[]; priced_position_count: number;
  unpriced_position_count: number; complete: boolean; completeness_notes: string[];
  daily_prices?: DailyPriceOverview | null;
};
export type ImportResult = { imported_count: number; errors: { row: number; field: string | null; message: string }[]; holdings: Holding[] };

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  let response: Response;
  const headers = new Headers(init.headers);
  if (!headers.has("Accept")) headers.set("Accept", "application/json");
  const token = sessionStorage.getItem("northstar_access_token");
  if (token && !headers.has("Authorization")) headers.set("Authorization", `Bearer ${token}`);
  try {
    response = await fetch(`${apiBaseUrl}${path}`, {
      ...init,
      headers,
    });
  } catch (cause) {
    if (cause instanceof DOMException && cause.name === "AbortError") throw cause;
    throw new Error(`Could not reach the API at ${apiBaseUrl}. Check that the backend is running.`);
  }
  if (!response.ok) {
    let message = `The API returned ${response.status} ${response.statusText || "error"}.`;
    let code: string | undefined;
    try {
      const body = await response.json() as { detail?: unknown };
      if (typeof body.detail === "string") message = body.detail;
      else if (Array.isArray(body.detail)) message = body.detail.map((item) => item.msg || "Invalid input").join(" ");
      else if (body.detail && typeof body.detail === "object") {
        const detail = body.detail as { message?: string; code?: string };
        if (typeof detail.message === "string") message = detail.message;
        if (typeof detail.code === "string") code = detail.code;
      }
    } catch { /* Keep the HTTP status message when the response has no JSON body. */ }
    const error = new Error(message) as ApiError;
    error.status = response.status;
    error.code = code;
    const retryAfter = Number(response.headers.get("Retry-After"));
    if (retryAfter > 0) error.retryAfter = retryAfter;
    throw error;
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export async function apiGet<T>(path: string, signal?: AbortSignal): Promise<T> {
  return request<T>(path, { method: "GET", signal });
}

export function apiPost<T>(path: string, body?: unknown) {
  return request<T>(path, { method: "POST", headers: body === undefined ? {} : { "Content-Type": "application/json" }, body: body === undefined ? undefined : JSON.stringify(body) });
}

export function apiPatch<T>(path: string, body: unknown) {
  return request<T>(path, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
}

export function apiDelete(path: string) {
  return request<void>(path, { method: "DELETE" });
}

export function apiUpload<T>(path: string, file: File, metadata?: unknown) {
  const body = new FormData();
  body.append("file", file);
  if (metadata !== undefined) body.append("metadata", JSON.stringify(metadata));
  return request<T>(path, { method: "POST", body });
}

export function apiPut<T>(path: string, body: unknown) {
  return request<T>(path, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
}

export function getHealth(signal?: AbortSignal) {
  return apiGet<HealthResponse>("/health", signal);
}

export { apiBaseUrl };
