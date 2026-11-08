import { StrictMode } from "react";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { apiDelete, apiGet, apiPost } from "../services/api";
import { IndmoneyConnect } from "./IndmoneyConnect";

vi.mock("../services/api", () => ({ apiGet: vi.fn(), apiPost: vi.fn(), apiDelete: vi.fn() }));
const base = "/integrations/indmoney";
afterEach(cleanup);
beforeEach(() => {
  vi.resetAllMocks(); sessionStorage.clear(); window.history.replaceState({}, "", "/portfolios");
  vi.mocked(apiGet).mockImplementation(async path => path.endsWith("/assets") ? { asset_types: ["IND_STOCK", "MF"] } : { configured: true, connected: true, last_sync_at: null });
});

describe("INDmoney holdings", () => {
  it("previews and imports PF as an account balance", async () => {
    vi.mocked(apiGet).mockImplementation(async path => path.endsWith("/assets") ? { asset_types: ["IND_STOCK", "EPF"] } : { configured: true, connected: true, last_sync_at: null });
    vi.mocked(apiPost).mockImplementation(async path => path.endsWith("/preview") ? {
      preview_id: "pf-1", expires_at: "2026-11-08T20:00:00Z", mode: "Preserves holdings", warnings: [],
      rows: [{ kind: "balance", symbol: "EPF-0001", display_name: "Employee provident fund", asset_type: "EPF", currency: "INR", market_value: "5500", conflict: false }],
    } : { added: 1, updated: 0, skipped: 0, warnings: [] });
    const refreshed = vi.fn().mockResolvedValue(undefined);
    render(<IndmoneyConnect portfolioId="p1" onSynced={refreshed} />);
    await waitFor(() => expect((screen.getByRole("button", { name: "Preview holdings" }) as HTMLButtonElement).disabled).toBe(false));
    await userEvent.selectOptions(screen.getByLabelText("Asset type"), "EPF");
    await userEvent.click(screen.getByRole("button", { name: "Preview holdings" }));
    expect(await screen.findByText("Employee provident fund")).toBeTruthy();
    expect(screen.getByText("Account balance")).toBeTruthy();
    expect(apiPost).toHaveBeenCalledWith(base + "/portfolios/p1/preview", { asset_type: "EPF" });
    await userEvent.click(screen.getByRole("button", { name: "Import reviewed holdings" }));
    await waitFor(() => expect(refreshed).toHaveBeenCalledOnce());
  });
  it("previews holdings before importing and refreshes portfolio after success", async () => {
    const refreshed = vi.fn().mockResolvedValue(undefined);
    vi.mocked(apiPost).mockImplementation(async path => path.endsWith("/preview") ? {
      preview_id: "preview-1", expires_at: "2026-11-07T20:00:00Z", mode: "Preserves manual holdings", warnings: ["Purchase cost unknown"],
      rows: [{ symbol: "INFY", exchange: "NSE", currency: "INR", quantity: "2", average_cost: null, conflict: false }],
    } : { added: 1, updated: 0, skipped: 0, warnings: [] });
    render(<IndmoneyConnect portfolioId="p1" onSynced={refreshed} />);
    await waitFor(() => expect((screen.getByRole("button", { name: "Preview holdings" }) as HTMLButtonElement).disabled).toBe(false));
    expect(screen.queryByRole("button", { name: "Import reviewed holdings" })).toBeNull();
    await userEvent.click(screen.getByRole("button", { name: "Preview holdings" }));
    await screen.findByText("INFY");
    expect(apiPost).toHaveBeenCalledWith(base + "/portfolios/p1/preview", { asset_type: "IND_STOCK" });
    expect(refreshed).not.toHaveBeenCalled();
    await userEvent.click(screen.getByRole("button", { name: "Import reviewed holdings" }));
    await screen.findByText("INDmoney: 1 added, 0 updated, 0 skipped.");
    expect(apiPost).toHaveBeenCalledWith(base + "/portfolios/p1/sync", { preview_id: "preview-1" });
    expect(refreshed).toHaveBeenCalledOnce();
  });

  it("exchanges a callback once under StrictMode and removes URL credentials", async () => {
    sessionStorage.setItem("indmoney_oauth_state", "state-123");
    window.history.replaceState({}, "", "/portfolios?code=one-use&state=state-123");
    vi.mocked(apiPost).mockResolvedValue({ connected: true });
    render(<StrictMode><IndmoneyConnect portfolioId="p1" onSynced={vi.fn()} /></StrictMode>);
    await screen.findByText("Connected");
    expect(apiPost).toHaveBeenCalledTimes(1);
    expect(apiPost).toHaveBeenCalledWith(base + "/callback", { code: "one-use", state: "state-123" });
    expect(window.location.search).toBe("");
    expect(sessionStorage.getItem("indmoney_oauth_state")).toBeNull();
  });

  it.each([
    { warnings: ["Row 1: skipped because missing or non-positive quantity."], message: "INDmoney returned holdings, but none could be imported. Review the import notes below." },
    { warnings: [], message: "No holdings returned by INDmoney for this asset type." },
  ])("explains an empty preview with $warnings.length import notes", async ({ warnings, message }) => {
    vi.mocked(apiPost).mockResolvedValue({
      preview_id: "empty-preview", expires_at: "2026-11-08T20:00:00Z", mode: "Preserves manual holdings", warnings, rows: [],
    });
    render(<IndmoneyConnect portfolioId="p1" onSynced={vi.fn()} />);
    await waitFor(() => expect((screen.getByRole("button", { name: "Preview holdings" }) as HTMLButtonElement).disabled).toBe(false));
    await userEvent.click(screen.getByRole("button", { name: "Preview holdings" }));
    expect(await screen.findByText(message)).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Import reviewed holdings" })).toBeNull();
    if (warnings.length) expect(screen.getByText(warnings[0])).toBeTruthy();
  });

  it("rejects callbacks from a different browser session", async () => {
    window.history.replaceState({}, "", "/portfolios?code=one-use&state=unexpected");
    render(<IndmoneyConnect portfolioId="p1" onSynced={vi.fn()} />);
    expect((await screen.findByRole("alert")).textContent).toContain("did not match");
    expect(apiPost).not.toHaveBeenCalled();
    expect(window.location.search).toBe("");
  });

  it("shows provider failures without importing or refreshing", async () => {
    const refreshed = vi.fn();
    vi.mocked(apiPost).mockRejectedValue(new Error("INDmoney session expired. Connect again."));
    render(<IndmoneyConnect portfolioId="p1" onSynced={refreshed} />);
    await waitFor(() => expect((screen.getByRole("button", { name: "Preview holdings" }) as HTMLButtonElement).disabled).toBe(false));
    await userEvent.click(screen.getByRole("button", { name: "Preview holdings" }));
    expect((await screen.findByRole("alert")).textContent).toContain("session expired");
    expect(refreshed).not.toHaveBeenCalled();
    expect(screen.queryByRole("button", { name: "Import reviewed holdings" })).toBeNull();
  });

  it("disconnects without deleting imported holdings", async () => {
    vi.mocked(apiDelete).mockResolvedValue(undefined);
    render(<IndmoneyConnect portfolioId="p1" onSynced={vi.fn()} />);
    await waitFor(() => expect((screen.getByRole("button", { name: "Disconnect" }) as HTMLButtonElement).disabled).toBe(false));
    await userEvent.click(screen.getByRole("button", { name: "Disconnect" }));
    await screen.findByText(/Imported holdings are retained/);
    expect(apiDelete).toHaveBeenCalledWith(base);
    expect(screen.queryByRole("button", { name: "Preview holdings" })).toBeNull();
  });
});
