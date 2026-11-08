import { apiPost } from "./api";
import type { Evidence } from "./research";

export type NewsArticle = { id: string; title: string; url: string; publisher: string; published_at: string };
export type NewsSignal = { title: string; text: string; source_ids: string[]; basis: string };
export type StockBrief = {
  kind: "stock"; holding_id: string; name: string; symbol: string; generated_at: string; view: string;
  pros: NewsSignal[]; cons: NewsSignal[]; evidence: Evidence[]; limitations: string[]; questions: string[];
  news: { status: "available" | "empty" | "unavailable"; articles: NewsArticle[]; checked_at: string; provider?: string; cached: boolean; note: string };
  portfolio_context: { cost_weight_pct: string | null; market_weight_pct: string | null };
};
export type PortfolioBrief = {
  kind: "portfolio"; name: string; generated_at: string; view: string; strengths: string[]; concerns: string[];
  stocks: StockBrief[]; limitations: string[]; questions: string[]; weight_basis: string; security_count: number; pf_account_count: number;
};
export type ResearchBrief = StockBrief | PortfolioBrief;

export function getBrief(portfolioId: string, holdingId?: string) {
  return apiPost<ResearchBrief>(holdingId ? `/portfolios/${portfolioId}/holdings/${holdingId}/brief` : `/portfolios/${portfolioId}/brief`);
}
