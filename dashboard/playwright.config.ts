import { defineConfig } from "@playwright/test";
/** Uses already running local services. Live tests require explicit provider opt-in. */
export default defineConfig({
  testDir: "./e2e", workers: 1, retries: 0, timeout: 900000,
  use: { baseURL: process.env.DEMO_WEB_URL || "http://localhost:3000", browserName: "chromium" },
});
