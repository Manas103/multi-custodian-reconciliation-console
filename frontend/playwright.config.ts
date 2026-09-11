import { defineConfig } from "@playwright/test";

// No global webServer here on purpose: this project's servers (the FastAPI
// backend and the Vite dev server) are started and stopped by the test
// itself, each on a free, OS-assigned port. Only Playwright's own bundled,
// headless Chromium is used; nothing here launches or looks for a real
// browser (BUILDER.md section 3a).
export default defineConfig({
  testDir: "./tests",
  timeout: 60_000,
  use: {
    headless: true,
  },
});
