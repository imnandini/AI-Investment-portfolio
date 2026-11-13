import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { CompanyFundamentals } from "./CompanyFundamentals";
import { apiGet } from "../services/api";
import { formatCompanyNumber, screenerTicker } from "../services/companyResearch";

vi.mock("../services/api", () => ({ apiGet: vi.fn() }));
afterEach(cleanup);
beforeEach(() => vi.clearAllMocks());
const snapshot = { status: "available", symbol: "AARTIIND", exchange: "NSE", name: "Aarti Industries Limited", provider: "Yahoo Finance via yfinance",
  retrieved_at: "2026-11-13T08:00:00Z", cached: false, source_url: "https://finance.yahoo.com/quote/AARTIIND.NS/",
  screener_url: "https://www.screener.in/company/AARTIIND/consolidated/", price: "480", price_as_of: null,
  metrics: [{ label: "Revenue", value: "10000000000", unit: "INR", period: "Trailing 12 months" },
    { label: "Return on equity", value: null, unit: "%", period: "Trailing 12 months" }], statements: [], notes: ["Reporting basis may differ."] };

describe("company fundamentals", () => {
  it("searches by name, confirms exchange and displays sourced financial details", async () => {
    vi.mocked(apiGet).mockImplementation(async path => path.includes("/search?")
      ? { status: "available", note: "Choose the correct company and exchange.", matches: [{ name: "Aarti Industries Limited", symbol: "AARTIIND", exchange: "NSE" }] } : snapshot);
    render(<CompanyFundamentals />);
    await userEvent.type(screen.getByLabelText("Company name, ticker or Screener URL"), "Aarti Industries");
    await userEvent.click(screen.getByRole("button", { name: "Search companies" }));
    await userEvent.click(await screen.findByRole("button", { name: "View Aarti Industries Limited on NSE" }));
    await screen.findByText("₹ 1,000 Cr");
    expect(screen.getByText("Unavailable")).toBeTruthy();
    expect(screen.getByText(/Price date: Not supplied/)).toBeTruthy();
    expect(screen.getByRole("link", { name: "Compare on Screener" }).getAttribute("href")).toBe(snapshot.screener_url);
    expect(screen.getByRole("link", { name: "View Yahoo Finance source" }).getAttribute("rel")).toContain("noopener");
    expect(apiGet).toHaveBeenCalledWith("/companies/search?q=Aarti%20Industries");
    expect(apiGet).toHaveBeenCalledWith("/companies/AARTIIND/snapshot?exchange=NSE");
  });

  it("resolves a Screener company link without fetching the supplied URL", async () => {
    vi.mocked(apiGet).mockResolvedValue(snapshot);
    render(<CompanyFundamentals />);
    await userEvent.type(screen.getByLabelText("Company name, ticker or Screener URL"), snapshot.screener_url);
    await userEvent.click(screen.getByRole("button", { name: "Search companies" }));
    await screen.findByText("₹ 1,000 Cr");
    expect(apiGet).toHaveBeenCalledTimes(1);
    expect(apiGet).toHaveBeenCalledWith("/companies/AARTIIND/snapshot?exchange=NSE");
  });

  it("shows provider failures and clears previous figures", async () => {
    vi.mocked(apiGet).mockResolvedValueOnce(snapshot).mockResolvedValueOnce({ ...snapshot, status: "unavailable", name: null, metrics: [], notes: ["Provider unavailable"] });
    render(<CompanyFundamentals symbol="AARTIIND" exchange="NSE" />);
    await userEvent.click(screen.getByRole("button", { name: "Show holding details" }));
    await screen.findByText("₹ 1,000 Cr");
    await userEvent.click(screen.getByRole("button", { name: "Show holding details" }));
    await screen.findByText("Provider unavailable");
    expect(screen.queryByText("₹ 1,000 Cr")).toBeNull();
  });

  it("validates URLs and formats amounts, percentages and EPS in distinct units", () => {
    expect(screenerTicker("https://www.screener.in/company/524208/")).toEqual({ symbol: "524208", exchange: "BSE" });
    for (const url of ["https://screener.in.attacker.com/company/AARTIIND/", "http://screener.in/company/AARTIIND/", "https://name:password@screener.in/company/AARTIIND/"]) {
      expect(() => screenerTicker(url)).toThrow();
    }
    expect(formatCompanyNumber("-10000000", "INR")).toBe("₹ -1 Cr");
    expect(formatCompanyNumber("7.1", "%")).toBe("7.1%");
    expect(formatCompanyNumber("16.35", "INR / share")).toBe("₹ 16.35");
    expect(formatCompanyNumber(null, "INR")).toBe("Unavailable");
  });
});
