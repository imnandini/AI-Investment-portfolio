import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { StrictMode } from "react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { getBrief, type StockBrief, type PortfolioBrief } from "../services/briefs";
import { ResearchBriefPanel } from "./ResearchBriefPanel";

vi.mock("../services/briefs", () => ({ getBrief: vi.fn() }));
afterEach(cleanup);
beforeEach(() => vi.clearAllMocks());

const stock: StockBrief = {
  kind: "stock", holding_id: "h1", name: "Acme Limited", symbol: "INDS0001", generated_at: "2026-11-08T10:00:00Z", view: "Mixed news signals for Acme.",
  pros: [{ title: "Earnings growth reported", text: "Check cash flows.", source_ids: ["news-1"], basis: "headline_signal" }],
  cons: [{ title: "Regulatory concern reported", text: "Check disclosures.", source_ids: ["news-2"], basis: "headline_signal" }],
  news: { status: "available", checked_at: "2026-11-08T10:00:00Z", cached: false, provider: "Synthetic news", note: "Headlines only", articles: [
    { id: "news-1", title: "Acme profit rises", url: "https://publisher.example/growth", publisher: "Example", published_at: "2026-11-08T09:00:00Z" },
    { id: "news-2", title: "Acme faces probe", url: "https://publisher.example/probe", publisher: "Example", published_at: "2026-11-08T08:00:00Z" },
  ] },
  portfolio_context: { cost_weight_pct: "80", market_weight_pct: null }, evidence: [], questions: ["Is cash flow recurring?"], limitations: ["Headlines are unverified."],
};

it("loads stock pros, cons and recent news without an upload or second click", async () => {
  vi.mocked(getBrief).mockResolvedValue(stock);
  render(<ResearchBriefPanel portfolioId="p1" holdingId="h1" name="Acme" onClose={vi.fn()} />);
  expect(await screen.findByText("Mixed news signals for Acme.")).toBeTruthy();
  expect(getBrief).toHaveBeenCalledWith("p1", "h1");
  expect(screen.getByRole("heading", { name: "Pros to investigate" })).toBeTruthy();
  expect(screen.getByText("Earnings growth reported")).toBeTruthy();
  expect(screen.getByText("Regulatory concern reported")).toBeTruthy();
  const link = screen.getAllByRole("link", { name: "Acme profit rises ↗" })[0];
  expect(link.getAttribute("href")).toBe("https://publisher.example/growth");
  expect(link.getAttribute("rel")).toContain("noreferrer");
  expect(screen.getByText(/80.0% of security cost basis/)).toBeTruthy();
});

it("shares one brief request across StrictMode effect replay", async () => {
  vi.mocked(getBrief).mockResolvedValue(stock);
  render(<StrictMode><ResearchBriefPanel portfolioId="p1" holdingId="h1" name="Acme" onClose={vi.fn()} /></StrictMode>);
  await screen.findByText("Mixed news signals for Acme.");
  expect(getBrief).toHaveBeenCalledOnce();
});

it("opens the portfolio opinion and expandable stock briefs", async () => {
  const portfolio: PortfolioBrief = { kind: "portfolio", name: "Long term", generated_at: stock.generated_at, view: "Concentration deserves attention.", strengths: [], concerns: ["Acme is 80% of cost basis."], stocks: [stock], limitations: [], questions: [], weight_basis: "cost basis", security_count: 2, pf_account_count: 1 };
  vi.mocked(getBrief).mockResolvedValue(portfolio);
  render(<ResearchBriefPanel portfolioId="p1" name="Long term" onClose={vi.fn()} />);
  expect(await screen.findByText("Concentration deserves attention.")).toBeTruthy();
  expect(getBrief).toHaveBeenCalledWith("p1", undefined);
  expect(screen.getByText("Acme is 80% of cost basis.")).toBeTruthy();
  await userEvent.click(screen.getByText("Acme Limited"));
  expect(screen.getByRole("heading", { name: "Pros to investigate" })).toBeTruthy();
});

it("shows failures, allows retry and closes the panel", async () => {
  vi.mocked(getBrief).mockRejectedValueOnce(new Error("Service unavailable")).mockResolvedValueOnce(stock);
  const close = vi.fn();
  render(<ResearchBriefPanel portfolioId="p1" holdingId="h1" name="Acme" onClose={close} />);
  expect((await screen.findByRole("alert")).textContent).toBe("Service unavailable");
  await userEvent.click(screen.getByRole("button", { name: "Refresh brief" }));
  await screen.findByText("Mixed news signals for Acme.");
  await userEvent.click(screen.getByRole("button", { name: "Close research brief" }));
  expect(close).toHaveBeenCalledOnce();
});

it("does not replace the new holding with an older pending response", async () => {
  let finishOld: (value: StockBrief) => void = () => {};
  vi.mocked(getBrief).mockImplementationOnce(() => new Promise(resolve => { finishOld = resolve; })).mockResolvedValueOnce({ ...stock, name: "Second company", view: "Second company view." });
  const { rerender } = render(<ResearchBriefPanel portfolioId="p1" holdingId="h1" name="Acme" onClose={vi.fn()} />);
  rerender(<ResearchBriefPanel portfolioId="p1" holdingId="h2" name="Second company" onClose={vi.fn()} />);
  await screen.findByText("Second company view.");
  finishOld(stock);
  await waitFor(() => expect(screen.queryByText("Mixed news signals for Acme.")).toBeNull());
});
