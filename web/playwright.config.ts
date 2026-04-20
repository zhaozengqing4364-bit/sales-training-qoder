import path from "node:path";

import { defineConfig, devices } from "@playwright/test";

const repoRoot = path.resolve(__dirname, "..");
const evidenceRoot = path.join(repoRoot, ".sisyphus", "evidence");
const evidencePrefix = process.env.SMOKE_EVIDENCE_PREFIX || "task-9";

export default defineConfig({
  testDir: path.join(__dirname, "tests", "e2e"),
  fullyParallel: false,
  workers: 1,
  timeout: 90_000,
  expect: {
    timeout: 15_000,
  },
  outputDir: path.join(evidenceRoot, `${evidencePrefix}-test-results`),
  reporter: [
    ["list"],
    [
      "html",
        {
          open: "never",
          outputFolder: path.join(evidenceRoot, `${evidencePrefix}-playwright-report`),
        },
      ],
  ],
  use: {
    baseURL: process.env.SMOKE_WEB_BASE_URL || "http://localhost:3445",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
    actionTimeout: 15_000,
    navigationTimeout: 30_000,
  },
  globalSetup: path.join(__dirname, "tests", "e2e", "global-setup.ts"),
  globalTeardown: path.join(__dirname, "tests", "e2e", "global-teardown.ts"),
  projects: [
    {
      name: "chromium",
      use: {
        ...devices["Desktop Chrome"],
      },
    },
  ],
});
