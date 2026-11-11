import { cleanup, render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, it, vi } from "vitest";
import { DashboardPage } from "./Dashboard";
import { apiGet, apiPost, type HoldingAnalytics } from "../services/api";

vi.mock("../components/AuthGate", () => ({ AuthGate: ({ children }: { children: React.ReactNode }) => children }));
vi.mock("../components/ApiStatus", () => ({ ApiStatus: () => null }));
vi.mock("../services/api", () => ({ apiGet: vi.fn(), apiPost: vi.fn() }));
afterEach(() => { cleanup(); vi.clearAllMocks(); });

const position: HoldingAnalytics = {
  symbol: "INDS01322", exchange: "UNKNOWN", asset_type: "EQUITY", sector: null, currency: "INR", quantity: "1", average_cost: "100", cost_basis: "100",
  current_price: "125", market_value: "125", unrealized_pl: "25", unrealized_return_pct: "25.00", market_allocation_pct: "56.82", cost_basis_allocation_pct: "50",
  price_as_of: "2026-11-10T00:00:00+05:30", price_status: "available",
};

function mockSummary(returnPct: string | null = "10.00") {
  vi.mocked(apiGet).mockImplementation(async path => path === "/portfolios" ? [{ id: "p1", name: "Long term", base_currency: "INR" }] : [
    { instrument: { canonical_symbol: "INDS01322", exchange: "UNKNOWN", display_name: "India Cements Capital Ltd" } },
    { instrument: { canonical_symbol: "INDS20549", exchange: "UNKNOWN", display_name: "CPSE ETF" } },
  ]);
  vi.mocked(apiPost).mockResolvedValue({ cost_basis_total: "200", market_value_total: "220", unrealized_pl_total: "20", unrealized_return_pct: returnPct, base_currency: "INR", complete: true,
    positions: [position, { ...position, symbol: "INDS20549", current_price: "95", market_value: "95", unrealized_pl: "-5", unrealized_return_pct: "-5.00" }],
    sector_mix: [{ name: "Unknown", allocation_pct: "100.00", cost_basis: "200" }], unpriced_position_count: 0 });
}

it("shows both investments and their returns, with the overall percentage on Overview", async () => {
  mockSummary();
  render(<MemoryRouter><DashboardPage /></MemoryRouter>);
  const holdings = await screen.findByRole("region", { name: "Portfolio holdings" });
  expect(within(holdings).getByText("India Cements Capital Ltd")).toBeTruthy();
  expect(within(holdings).getByText("CPSE ETF")).toBeTruthy();
  expect(within(holdings).getByText("+25.00%")).toBeTruthy();
  expect(within(holdings).getByText("-5.00%")).toBeTruthy();
  expect(screen.getByText("+10.00%")).toBeTruthy();
  expect(screen.getByText(/sector information has not been supplied/)).toBeTruthy();
  expect(apiGet).toHaveBeenCalledWith("/portfolios/p1/holdings");
});

it("does not replace an unknown portfolio return with zero", async () => {
  mockSummary(null);
  render(<MemoryRouter><DashboardPage /></MemoryRouter>);
  await screen.findByRole("region", { name: "Portfolio holdings" });
  const label = screen.getByText("Return %", { selector: "span" });
  expect(label.parentElement?.textContent).toContain("—");
  expect(label.parentElement?.textContent).not.toContain("0.00%");
});
