import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { CompanyResearchPage } from "./CompanyResearch";
import { PortfolioReviewPage } from "./PortfolioReview";
import { ResearchChatPage } from "./ResearchChat";
import { EvidencePanel } from "../components/EvidencePanel";
import { apiGet, apiPost } from "../services/api";
import { getReviews, launchReview } from "../services/reviews";

vi.mock("../components/AuthGate", () => ({ AuthGate: ({ children }: { children: React.ReactNode }) => children }));
vi.mock("../services/api", () => ({ apiGet: vi.fn(), apiPost: vi.fn(), apiUpload: vi.fn(), apiDelete: vi.fn() }));
vi.mock("../services/reviews", () => ({ getReviews: vi.fn(), launchReview: vi.fn() }));
afterEach(cleanup);
beforeEach(() => vi.clearAllMocks());
const evidence = { chunk_id: "chunk-1", document_id: "doc-1", title: "Synthetic report", company: "AAA", page: 3, period: "FY2026", publication_date: "2026-01-01", source_url: "https://example.org/report", text: "Revenue increased.", score: 1 };

describe("research flows", () => {
  it("renders citations as text and opens the source safely", async () => {
    render(<EvidencePanel evidence={[{ ...evidence, text: "<script>alert(1)</script>" }]} />);
    await userEvent.click(screen.getByText(/Synthetic report · page 3/));
    expect(screen.getByText("<script>alert(1)</script>")).toBeTruthy();
    expect(screen.getByRole("link", { name: "Open original source" }).getAttribute("rel")).toContain("noreferrer");
    expect(document.querySelector("script")).toBeNull();
  });
  it("shows an empty library and insufficient-evidence answer", async () => {
    vi.mocked(apiGet).mockResolvedValue([]);
    vi.mocked(apiPost).mockResolvedValue({ answer: "Insufficient evidence for this question.", evidence: [], limitations: ["Upload a relevant PDF."], activities: [], status: "insufficient_evidence", method: "extractive-v1" });
    render(<CompanyResearchPage />);
    await screen.findByText(/No documents yet/);
    await userEvent.type(screen.getByLabelText("Question"), "What is revenue?");
    await userEvent.click(screen.getByRole("button", { name: "Find evidence" }));
    await screen.findByText("Insufficient evidence for this question.");
    expect(apiPost).toHaveBeenCalledWith("/documents/answer", expect.objectContaining({ query: "What is revenue?" }));
  });
  it("launches and reopens a saved partial review", async () => {
    vi.mocked(apiGet).mockResolvedValue([{ id: "p1", name: "My portfolio" }]);
    vi.mocked(getReviews).mockResolvedValue([]);
    vi.mocked(launchReview).mockResolvedValue({ id: "r1", portfolio_id: "p1", status: "partial", created_at: "2026-01-01", report: { methodology_version: "v1", summary: "Saved report", findings: [], evidence: [evidence], limitations: ["Price data missing"], follow_up_questions: ["Which data needs updating?"], activities: [], analytics: { methodology: "Decimal calculations" } } } as never);
    render(<PortfolioReviewPage />);
    await waitFor(() => expect((screen.getByRole("button", { name: "Start review" }) as HTMLButtonElement).disabled).toBe(false));
    await userEvent.click(screen.getByRole("button", { name: "Start review" }));
    await screen.findByText("Saved report");
    expect(screen.getByText("Price data missing")).toBeTruthy();
    expect(launchReview).toHaveBeenCalledWith("p1");
  });
  it("keeps API failures visible in chat", async () => {
    vi.mocked(apiGet).mockImplementation(async path => path === "/portfolios" ? [{ id: "p1", name: "My portfolio" }] : []);
    vi.mocked(apiPost).mockRejectedValue(new Error("Search service unavailable"));
    render(<ResearchChatPage />);
    await waitFor(() => expect((screen.getByRole("button", { name: "Ask question" }) as HTMLButtonElement).disabled).toBe(false));
    await userEvent.type(screen.getByLabelText("Your question"), "What is revenue?");
    await userEvent.click(screen.getByRole("button", { name: "Ask question" }));
    expect((await screen.findByRole("alert")).textContent).toBe("Search service unavailable");
  });
});
