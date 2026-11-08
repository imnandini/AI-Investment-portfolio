import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";
import { PortfolioPage } from "./Portfolio";
import { apiGet, apiPost } from "../services/api";

vi.mock("../components/AuthGate", () => ({ AuthGate: ({ children }: { children: React.ReactNode }) => children }));
vi.mock("../components/IndmoneyConnect", () => ({ IndmoneyConnect: () => null }));
vi.mock("../components/ResearchBriefPanel", () => ({ ResearchBriefPanel: ({ holdingId }: { holdingId?: string }) => <section aria-label="Research brief">Brief for {holdingId || "portfolio"}</section> }));
vi.mock("../services/api", () => ({ apiGet: vi.fn(), apiPost: vi.fn(), apiUpload: vi.fn() }));
afterEach(cleanup);

it("shows company names, clear missing metadata and per-holding research beside PF balances", async () => {
  vi.mocked(apiGet).mockImplementation(async path => {
    if (path === "/portfolios") return [{ id: "p1", name: "Long term", base_currency: "INR" }];
    if (path.endsWith("/balances")) return [{ symbol: "EPF-0001", display_name: "Provident fund", asset_type: "EPF", currency: "INR", invested_amount: "5000", market_value: "5500", as_of: null, imported_at: "2026-11-08T10:00:00Z" }];
    return [{ id: "h1", quantity: "2", average_cost: "100", instrument: { canonical_symbol: "INDS00001", display_name: "Synthetic Company", exchange: "UNKNOWN", currency: "INR", asset_type: "EQUITY", sector: null } }];
  });
  vi.mocked(apiPost).mockResolvedValue({ cost_basis_total: "200", base_currency: "INR", positions: [{ symbol: "INDS00001", exchange: "UNKNOWN", price_status: "unknown_freshness", cost_basis: "200" }], asset_mix: [], sector_mix: [], completeness_notes: [], priced_position_count: 0, unpriced_position_count: 1 });
  render(<PortfolioPage />);
  expect(await screen.findByText("Synthetic Company")).toBeTruthy();
  expect(screen.getByText(/Exchange not supplied · EQUITY/)).toBeTruthy();
  expect(screen.getByText("Price date not supplied")).toBeTruthy();
  expect(screen.getByText("Provident fund")).toBeTruthy();
  const research = screen.getByRole("link", { name: "Research Synthetic Company" });
  const url = new URL(research.getAttribute("href")!, "http://localhost");
  expect(url.searchParams.get("holding")).toBe("INDS00001");
  expect(url.searchParams.get("name")).toBe("Synthetic Company");
  expect(url.searchParams.has("exchange")).toBe(false);
  expect(screen.getByRole("link", { name: "Research Provident fund" })).toBeTruthy();
  await userEvent.click(screen.getByRole("button", { name: "Pros, cons and news for Synthetic Company" }));
  expect(await screen.findByText("Brief for h1")).toBeTruthy();
  await waitFor(() => expect((screen.getByRole("button", { name: "Portfolio opinion" }) as HTMLButtonElement).disabled).toBe(false));
  await userEvent.click(screen.getByRole("button", { name: "Portfolio opinion" }));
  expect(await screen.findByText("Brief for portfolio")).toBeTruthy();
});
