import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, it } from "vitest";
import type { HoldingAnalytics } from "../services/api";
import { HoldingReturn } from "./HoldingReturn";

afterEach(cleanup);
const position: HoldingAnalytics = {
  symbol: "AAA", exchange: "NSE", asset_type: "EQUITY", sector: null, currency: "INR", quantity: "2", average_cost: "100", cost_basis: "200",
  current_price: "125", market_value: "250", unrealized_pl: "50", unrealized_return_pct: "25.00", market_allocation_pct: "100", cost_basis_allocation_pct: "100",
  price_as_of: "2026-11-10T00:00:00+05:30", price_status: "available",
};

it.each([["25.00", "+25.00%"], ["-10.00", "-10.00%"], ["0.00", "0.00%"]])("displays a signed holding return of %s", (value, expected) => {
  render(<table><tbody><tr><HoldingReturn position={{ ...position, unrealized_return_pct: value }} currency="INR" /></tr></tbody></table>);
  expect(screen.getByText(expected)).toBeTruthy();
});

it("keeps an unavailable return explicit when cost is unknown", () => {
  render(<table><tbody><tr><HoldingReturn position={{ ...position, average_cost: null, unrealized_pl: null, unrealized_return_pct: null }} currency="INR" /></tr></tbody></table>);
  expect(screen.getByText("Unavailable")).toBeTruthy();
  expect(screen.getByTitle("Purchase cost is unknown.")).toBeTruthy();
});

it("does not show a cached percentage from a stale price", () => {
  render(<table><tbody><tr><HoldingReturn position={{ ...position, price_status: "stale" }} currency="INR" /></tr></tbody></table>);
  expect(screen.queryByText("+25.00%")).toBeNull();
  expect(screen.getByText("Unavailable")).toBeTruthy();
});
