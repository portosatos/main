import { defineConfig, devices } from "@playwright/test";

import { BASE_URL, TIMEZONE } from "./lib/env";

// E2E of SPEC §8 stage 12 against the e2e stack (docker-compose.e2e.yml, scripts/e2e.*), and the
// screenshots of the pages with the 375 px check (screenshots.spec.ts, stage 13).
// One worker: the dev Clock is one for the whole stack, and scenarios that move it (12.2) must not
// overlap with others; the upload scenarios also measure timing and should not compete for the worker.
export default defineConfig({
  testDir: ".",
  testMatch: /(\d\d-[\w-]+|screenshots)\.spec\.ts$/,
  fullyParallel: false,
  workers: 1,
  forbidOnly: !!process.env.CI,
  retries: 0,
  timeout: 120_000,
  expect: { timeout: 10_000 },
  reporter: [["list"], ["html", { open: "never" }]],
  use: {
    baseURL: BASE_URL,
    // The browser's zone becomes the user's zone at registration (SPEC F1); htgen writes the same.
    timezoneId: TIMEZONE,
    locale: "ru-RU",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
});
