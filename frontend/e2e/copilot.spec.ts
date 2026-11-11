import { test, expect } from "@playwright/test";
import fs from "node:fs";

let disposableEmail = "";
const disposablePassword = process.env.E2E_PASSWORD || "";
test.afterEach(async ({ request }) => {
  if (!disposableEmail) return;
  const login = await request.post("/api/auth/login", { data: { email: disposableEmail, password: disposablePassword } });
  if (login.ok()) {
    const { access_token } = await login.json();
    await request.delete("/api/auth/me", { headers: { Authorization: `Bearer ${access_token}` } });
  }
});

test("account, holdings, source search, chat and saved review", async ({ page }) => {
  test.skip(!process.env.E2E_EMAIL || !disposablePassword, "Set E2E_EMAIL and E2E_PASSWORD to a disposable, email-verified account. This test deletes that account.");
  const email = process.env.E2E_EMAIL!;
  disposableEmail = email;
  await page.goto("/portfolios");
  await page.getByLabel(/Email/i).fill(email);
  await page.getByLabel("Password", { exact: true }).fill(disposablePassword);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.getByRole("region", { name: "Portfolio overview" })).toBeVisible();
  await page.getByRole("button", { name: "Create portfolio", exact: true }).click();
  await page.getByLabel("Portfolio name").fill("SYNTHETIC demo portfolio");
  await page.getByRole("button", { name: "Create", exact: true }).click();
  await page.locator('input[type="file"]').setInputFiles({ name: "synthetic-holdings.csv", mimeType: "text/csv", buffer: fs.readFileSync(new URL("../../sample_data/synthetic_holdings.csv", import.meta.url)) });
  await expect(page.getByText("1 holding imported.")).toBeVisible();
  await expect(page.getByRole("cell", { name: "AAA NSE · EQUITY · Technology" })).toBeVisible();
  await page.getByRole("navigation", { name: "Main navigation" }).getByRole("link", { name: "Research", exact: true }).click();
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
  await page.getByRole("link", { name: "Portfolio chat", exact: true }).click();
  await page.getByLabel("Your question").fill("What do my uploaded reports say about revenue risk?");
  await page.getByRole("button", { name: "Ask question" }).click();
  await expect(page.getByText(/Relevant source passages:/)).toBeVisible();
  await page.getByRole("link", { name: "Portfolio reviews", exact: true }).click();
  await page.getByRole("button", { name: "Start review" }).click();
  await expect(page.getByRole("heading", { name: /concentration deserves attention/ })).toBeVisible();
  await page.reload();
  await expect(page.getByRole("heading", { name: /concentration deserves attention/ })).toBeVisible();
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
