import { apiGet, apiPost } from "./api";
import type { PortfolioAnalytics } from "./api";
import type { Evidence } from "./research";
import type { NewsArticle, NewsSignal } from "./briefs";

export type ReviewCoverage = { total_positions: number; eligible_positions: number; selected_positions: number; checked_positions: number; positions_with_news: number; positions_without_news: number; unreviewed_positions: number; excluded_positions: number; checked_weight_pct: string | null; weight_basis: string; article_count: number; selection_policy: string };
export type CompanyReview = { name: string; symbol: string; exchange: string; is_fund: boolean; weight_pct: string | null; weight_basis: string; unrealized_return_pct: string | null; price_as_of: string | null; view: string; portfolio_impact: string; positive_signals: NewsSignal[]; concern_signals: NewsSignal[]; news: { status: "available" | "empty" | "unavailable" | "not_checked"; checked_at: string | null; provider?: string | null; cached?: boolean; note: string; articles: NewsArticle[] } };
export type Review = { id: string; portfolio_id: string; status: string; created_at: string; report: { error?: string; methodology_version: string; generated_at?: string | null; assessment_status?: string; summary: string; analytics: PortfolioAnalytics; findings: { title: string; text: string; basis: string; evidence_indices: number[]; source_ids?: string[] }[]; evidence: Evidence[]; limitations: string[]; follow_up_questions: string[]; activities: string[]; coverage?: ReviewCoverage | null; company_reviews?: CompanyReview[] } | null };
export const getReviews = (id: string, signal?: AbortSignal) => apiGet<Review[]>(`/portfolios/${id}/reviews`, signal);
export const launchReview = (id: string) => apiPost<Review>(`/portfolios/${id}/reviews`);
