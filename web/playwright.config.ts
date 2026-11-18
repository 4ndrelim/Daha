import { defineConfig, devices } from "@playwright/test";

/**
 * End-to-end smoke test (PLAN.md §2 P1 #6). Runs against an app that is already up:
 *   make db migrate seed && make api   (AI_PROVIDER=mock, COMMERCIAL_PROVIDER=mock: free)
 *   make web
 *   cd web && pnpm e2e
 * E2E_BASE_URL points it somewhere else (e.g. the tunnel link).
 */
export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  expect: { timeout: 15_000 },
  retries: 0,
  reporter: [["list"]],
  use: {
    baseURL: process.env.E2E_BASE_URL ?? "http://localhost:3000",
    trace: "retain-on-failure",
  },
  projects: [{ name: "phone", use: { ...devices["Pixel 7"] } }],
});
