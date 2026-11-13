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
beforeEach(() => { vi.clearAllMocks(); window.history.replaceState({}, "", "/research"); });
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
    expect(screen.getByText(/older document-based format/)).toBeTruthy();
    expect(screen.getByText("Price data missing")).toBeTruthy();
    expect(launchReview).toHaveBeenCalledWith("p1");
  });
  it("shows a saved news review without requiring uploaded documents", async () => {
    vi.mocked(apiGet).mockResolvedValue([{ id: "p1", name: "My portfolio" }]);
    vi.mocked(getReviews).mockResolvedValue([]);
    vi.mocked(launchReview).mockResolvedValue({ id: "r2", portfolio_id: "p1", status: "partial", created_at: "2026-11-11T10:00:00Z", report: {
      methodology_version: "portfolio-review-v2", summary: "Acme concentration deserves attention", analytics: { methodology: "Saved calculations" },
      findings: [{ title: "Price sensitivity", text: "A 10% fall in Acme would reduce this basket by about 6.67%.", basis: "calculation", evidence_indices: [], source_ids: [] }],
      evidence: [], limitations: ["Sector data is incomplete"], follow_up_questions: ["Does Acme match your intended exposure?"], activities: ["Checked news"],
      coverage: { total_positions: 100, eligible_positions: 100, selected_positions: 20, checked_positions: 20, positions_with_news: 18, positions_without_news: 2, unreviewed_positions: 80, excluded_positions: 0, checked_weight_pct: "65.00", weight_basis: "market value", article_count: 25, selection_policy: "Largest holdings first, up to 20." },
      company_reviews: [{ name: "Acme Limited", symbol: "AAA", exchange: "NSE", is_fund: false, weight_pct: "66.67", weight_basis: "market value", unrealized_return_pct: "10.00", price_as_of: "2026-11-10T00:00:00Z", view: "Recent Acme developments", portfolio_impact: "Acme drives much of this portfolio's exposure.", positive_signals: [], concern_signals: [], news: {
        status: "available", checked_at: "2026-11-11T09:00:00Z", provider: "Test news", cached: false, note: "Matched headlines",
        articles: [{ id: "n1", title: "Acme reports quarterly results", url: "https://example.org/results", publisher: "Example News", published_at: "2026-11-10T09:00:00Z" }],
      } }],
    } } as never);
    render(<PortfolioReviewPage />);
    await waitFor(() => expect((screen.getByRole("button", { name: "Start review" }) as HTMLButtonElement).disabled).toBe(false));
    await userEvent.click(screen.getByRole("button", { name: "Start review" }));
    await screen.findByText("Acme concentration deserves attention");
    expect(screen.getByText(/100 positions calculated · 20 \/ 100/)).toBeTruthy();
    expect(screen.getByText(/80 listed holdings were not news-checked/)).toBeTruthy();
    expect(screen.getByText(/A 10% fall in Acme.*6\.67%/)).toBeTruthy();
    const source = screen.getByRole("link", { name: "Acme reports quarterly results" });
    expect(source.getAttribute("href")).toBe("https://example.org/results");
    expect(source.getAttribute("rel")).toContain("noopener");
    expect(screen.getByText(/Example News · Published/)).toBeTruthy();
    expect(screen.queryByText("No supporting passages found.")).toBeNull();
    expect(screen.queryByText(/older document-based format/)).toBeNull();
    expect(screen.getByText(/Documents are optional/)).toBeTruthy();
  });
  it("opens named INDmoney research without treating its internal code as an exchange ticker", async () => {
    window.history.replaceState({}, "", "/research?holding=INDS00001&name=Synthetic%20Company");
    vi.mocked(apiGet).mockResolvedValue([]);
    vi.mocked(apiPost).mockResolvedValue({ answer: "Insufficient evidence.", evidence: [], limitations: [] });
    render(<CompanyResearchPage />);
    expect(screen.getByRole("heading", { name: "Synthetic Company" })).toBeTruthy();
    expect((screen.getByLabelText("Company name, ticker or Screener URL") as HTMLInputElement).value).toBe("Synthetic Company");
    expect((screen.getByLabelText("Company / ticker") as HTMLInputElement).value).toBe("INDS00001");
    expect((screen.getByLabelText("Company filter") as HTMLInputElement).value).toBe("INDS00001");
    expect(screen.getByRole("link", { name: "Search web sources" }).getAttribute("href")).toContain("Synthetic%20Company");
    await userEvent.click(screen.getByRole("button", { name: "Find evidence" }));
    await waitFor(() => expect(apiPost).toHaveBeenCalledWith("/documents/answer", expect.objectContaining({ company: "INDS00001" })));
    expect(apiGet).not.toHaveBeenCalledWith(expect.stringContaining("/companies/"));
  });
  it("researches PF rules without using a private account label in web search", async () => {
    window.history.replaceState({}, "", "/research?holding=EPF-012345&name=Private%20Account%20Label");
    vi.mocked(apiGet).mockResolvedValue([]);
    render(<CompanyResearchPage />);
    expect(screen.queryByRole("heading", { name: "Company lookup" })).toBeNull();
    const search = screen.getByRole("link", { name: "Search web sources" });
    expect(search.getAttribute("href")).toContain("EPFO");
    expect(search.getAttribute("href")).not.toContain("Private");
  });
  it("keeps API failures visible in chat", async () => {
    vi.mocked(apiGet).mockImplementation(async path => path === "/portfolios" ? [{ id: "p1", name: "My portfolio" }] : []);
    vi.mocked(apiPost).mockRejectedValue(new Error("Search service unavailable"));
    render(<ResearchChatPage />);
    await waitFor(() => expect((screen.getByLabelText("Your question") as HTMLTextAreaElement).disabled).toBe(false));
    await userEvent.type(screen.getByLabelText("Your question"), "What is revenue?");
    await userEvent.click(screen.getByRole("button", { name: "Ask question" }));
    expect((await screen.findByRole("alert")).textContent).toBe("Search service unavailable");
  });
  it("asks a portfolio question without uploaded documents and displays dated news sources", async () => {
    vi.mocked(apiGet).mockImplementation(async path => path === "/portfolios" ? [{ id: "p1", name: "My portfolio" }] : []);
    vi.mocked(apiPost).mockResolvedValue({ id: "c1", question: "Is my overall portfolio okay?", created_at: "2026-11-11T10:00:00Z", response: {
      answer: "Acme represents 80% of security cost basis. Concentration deserves attention.",
      status: "supported", method: "portfolio-chat-v1", evidence: [], activities: ["Calculated saved metrics"], limitations: ["Prices are incomplete"],
      portfolio_context: { name: "My portfolio", position_count: 2, cost_basis: "1000", currency: "INR" },
      news: [{ name: "Acme", symbol: "ACME", status: "available", checked_at: "2026-11-11T09:00:00Z", cached: false, note: "Matched headlines", provider: "Example feed",
        articles: [{ id: "news-1", title: "Acme reports quarterly results", url: "https://example.org/results", publisher: "Example News", published_at: "2026-11-10T09:00:00Z" }] }],
    } });
    render(<ResearchChatPage />);
    expect(screen.getByText(/No document upload needed/)).toBeTruthy();
    const starter = screen.getByRole("button", { name: "Is my overall portfolio okay?" });
    await waitFor(() => expect((starter as HTMLButtonElement).disabled).toBe(false));
    await userEvent.click(starter);
    expect((screen.getByLabelText("Your question") as HTMLTextAreaElement).value).toBe("Is my overall portfolio okay?");
    await userEvent.click(screen.getByRole("button", { name: "Ask question" }));
    await screen.findByText(/Acme represents 80%/);
    expect(apiPost).toHaveBeenCalledWith("/portfolios/p1/chat", { question: "Is my overall portfolio okay?" });
    const source = screen.getByRole("link", { name: "Acme reports quarterly results" });
    expect(source.getAttribute("href")).toBe("https://example.org/results");
    expect(source.getAttribute("rel")).toContain("noopener");
    expect(screen.getByText(/Example News · Published/)).toBeTruthy();
    expect(screen.queryByText("No supporting passages found.")).toBeNull();
    await userEvent.click(screen.getByText("Data gaps & limitations"));
    expect(screen.getByText("Prices are incomplete")).toBeTruthy();
  });
});
