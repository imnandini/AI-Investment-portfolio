import { apiGet, apiPost } from "./api";
import type { PortfolioAnalytics } from "./api";
import type { Evidence } from "./research";
export type Review = { id: string; portfolio_id: string; status: string; created_at: string; report: { error?: string; methodology_version: string; summary: string; analytics: PortfolioAnalytics; findings: { title: string; text: string; basis: string; evidence_indices: number[] }[]; evidence: Evidence[]; limitations: string[]; follow_up_questions: string[]; activities: string[] } | null };
export const getReviews = (id: string, signal?: AbortSignal) => apiGet<Review[]>(`/portfolios/${id}/reviews`, signal);
export const launchReview = (id: string) => apiPost<Review>(`/portfolios/${id}/reviews`);
