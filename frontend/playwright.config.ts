import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "./e2e", workers: 1, retries: 0, timeout: 60000,
  use: { baseURL: process.env.E2E_UI_URL || "http://127.0.0.1:8080", headless: true, screenshot: "only-on-failure", trace: "retain-on-failure" },
});
