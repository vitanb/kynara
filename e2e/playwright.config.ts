import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./tests",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 4 : undefined,
  reporter: [["list"], ["html", { open: "never" }]],
  use: {
    baseURL: process.env.KYNARA_FRONTEND_URL || "http://localhost:5173",
    trace: "on-first-retry",
    video: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] } },
    { name: "firefox",  use: { ...devices["Desktop Firefox"] } },
  ],
  webServer: process.env.CI ? undefined : [
    {
      command: "cd ../backend && uvicorn app.main:app --port 8000",
      port: 8000, reuseExistingServer: true,
    },
    {
      command: "cd ../frontend && npm run dev",
      port: 5173, reuseExistingServer: true,
    },
  ],
});
