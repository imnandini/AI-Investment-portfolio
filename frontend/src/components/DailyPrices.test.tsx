import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, it } from "vitest";
import { DailyPrices } from "./DailyPrices";
import type { DailyPriceOverview } from "../services/api";

afterEach(cleanup);
const overview: DailyPriceOverview = {
  configured: true, provider: "Yahoo Finance daily closes", requested_through: "2026-11-10", latest_date: "2026-11-10",
  checked_at: "2026-11-11T08:00:00Z", covered_positions: 2, position_count: 2,
  notes: ["Weekends may have no new close."], comparison_basis: "Current quantities revalued at historical closes.",
  comparisons: [{ label: "Previous trading close", from_date: "2026-11-09", to_date: "2026-11-10", previous_value: "1000", latest_value: "1100", change: "100", change_pct: "10.00" }],
};

it("shows dated automatic prices and comparisons without a price-entry form", () => {
  render(<DailyPrices overview={overview} currency="INR" />);
  expect(screen.getByRole("region", { name: "Daily price updates" })).toBeTruthy();
  expect(screen.getByText(/No daily price entry needed/)).toBeTruthy();
  expect(screen.getByText("2026-11-09 → 2026-11-10")).toBeTruthy();
  expect(screen.getByText("+10.00%")).toBeTruthy();
  expect(screen.getByText(/Current quantities/)).toBeTruthy();
  expect(screen.queryByRole("spinbutton")).toBeNull();
});

it("keeps missing price coverage visible instead of inventing a comparison", () => {
  render(<DailyPrices overview={{ ...overview, covered_positions: 1, comparisons: [], notes: ["Other Company: no unique company match was found."] }} currency="INR" />);
  expect(screen.getByText(/1 \/ 2 with daily history/)).toBeTruthy();
  expect(screen.getByText(/no unique company match/)).toBeTruthy();
  expect(screen.getByText("Price coverage & update details").parentElement?.hasAttribute("open")).toBe(true);
  expect(screen.queryByText("How have prices changed?")).toBeNull();
});
