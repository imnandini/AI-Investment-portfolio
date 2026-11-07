import { test, expect } from "@playwright/test";
import fs from "node:fs";

let disposableEmail = "";
test.afterEach(async ({ request }) => {
  if (!disposableEmail) return;
  const login = await request.post("/api/auth/login", { data: { email: disposableEmail, password: "synthetic-e2e-password-2026" } });
  if (login.ok()) {
    const { access_token } = await login.json();
    await request.delete("/api/auth/me", { headers: { Authorization: `Bearer ${access_token}` } });
  }
});

test("account, holdings, source search, chat and saved review", async ({ page }) => {
  const email = `e2e-${Date.now()}@example.com`;
  disposableEmail = email;
  await page.goto("/portfolios");
  await page.getByRole("button", { name: /Create an account/i }).click();
  await page.getByLabel(/Email/i).fill(email);
  await page.getByLabel(/Password/i).fill("synthetic-e2e-password-2026");
  await page.getByRole("button", { name: /Create account/i, exact: true }).click();
  await expect(page.getByRole("heading", { name: "Your portfolios" })).toBeVisible();
  await page.getByRole("button", { name: "Create portfolio", exact: true }).click();
  await page.getByLabel("Portfolio name").fill("SYNTHETIC demo portfolio");
  await page.getByRole("button", { name: "Create", exact: true }).click();
  await page.locator('input[type="file"]').setInputFiles({ name: "synthetic-holdings.csv", mimeType: "text/csv", buffer: fs.readFileSync(new URL("../../sample_data/synthetic_holdings.csv", import.meta.url)) });
  await expect(page.getByText("1 holding imported.")).toBeVisible();
  await expect(page.getByRole("cell", { name: "AAA NSE · EQUITY · Technology" })).toBeVisible();
  await page.getByRole("link", { name: "Research", exact: true }).click();
  await page.getByLabel("Title", { exact: true }).fill("SYNTHETIC annual report");
  await page.getByLabel("Company / ticker").fill("AAA");
  await page.getByLabel("Reporting period").fill("FY2026");
  await page.getByLabel("PDF file").setInputFiles({ name: "synthetic.pdf", mimeType: "application/pdf", buffer: fs.readFileSync(new URL("../../sample_data/synthetic_report.pdf", import.meta.url)) });
  await page.getByRole("button", { name: "Upload and index" }).click();
  await expect(page.getByText(/Indexed 1 pages from/)).toBeVisible();
  await page.getByLabel("Question", { exact: true }).fill("revenue");
  await page.getByRole("button", { name: "Find evidence" }).click();
  await expect(page.getByText(/Relevant source passages:/)).toBeVisible();
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({ path: "../evaluation/reports/research-desktop.png", fullPage: true });
  await page.getByRole("link", { name: "Research chat", exact: true }).click();
  await page.getByLabel("Your question").fill("revenue risk");
  await page.getByRole("button", { name: "Ask question" }).click();
  await expect(page.getByText(/Relevant source passages:/)).toBeVisible();
  await page.getByRole("link", { name: "Portfolio reviews", exact: true }).click();
  await page.getByRole("button", { name: "Start review" }).click();
  await expect(page.getByRole("heading", { name: "Portfolio structure and source excerpts for research follow-up." })).toBeVisible();
  await page.reload();
  await expect(page.getByRole("heading", { name: "Portfolio structure and source excerpts for research follow-up." })).toBeVisible();
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({ path: "../evaluation/reports/review-desktop.png", fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.screenshot({ path: "../evaluation/reports/review-mobile.png", fullPage: true });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  // Only remove the disposable account created by this test.
  const response = await page.evaluate(async () => {
    const token = sessionStorage.getItem("northstar_access_token");
    return (await fetch("/api/auth/me", { method: "DELETE", headers: { Authorization: `Bearer ${token}` } })).status;
  });
  expect(response).toBe(204);
});
