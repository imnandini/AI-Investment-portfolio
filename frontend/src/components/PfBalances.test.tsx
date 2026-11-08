import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, it } from "vitest";
import { PfBalances } from "./PfBalances";

afterEach(cleanup);

it("displays PF balances with missing provider date and a research link", () => {
  render(<PfBalances balances={[{ symbol: "EPF-0001", display_name: "Provident fund", asset_type: "EPF", currency: "INR", invested_amount: null, market_value: "5500", as_of: null, imported_at: "2026-11-08T10:00:00Z" }]} />);
  expect(screen.getByText("Provident fund")).toBeTruthy();
  expect(screen.getByText("Not supplied by INDmoney")).toBeTruthy();
  const link = screen.getByRole("link", { name: "Research Provident fund" });
  const url = new URL(link.getAttribute("href")!, "http://localhost");
  expect(url.pathname).toBe("/research");
  expect(url.searchParams.get("holding")).toBe("EPF-0001");
  expect(screen.queryByRole("columnheader", { name: "Quantity" })).toBeNull();
});
