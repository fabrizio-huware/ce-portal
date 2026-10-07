import { defineConfig } from "@playwright/test";

/**
 * Test nel browser (end-to-end). Servono: backend in esecuzione con i dati di esempio (`make demo`) e
 * il frontend (`npm run build && npm run preview`, porta 4173).
 *
 * Prima volta:  npx playwright install chromium
 * Lancio:       npm run test:e2e
 */
const executablePath = process.env.E2E_CHROMIUM_PATH; // solo per ambienti con un Chromium già installato
const extraArgs: string[] = process.env.E2E_CHROMIUM_ARGS ? JSON.parse(process.env.E2E_CHROMIUM_ARGS) : [];

export default defineConfig({
  testDir: "./e2e",
  globalSetup: "./e2e/global-setup.ts",
  timeout: 30_000,
  expect: { timeout: 8_000 },
  fullyParallel: false,
  workers: 1,
  reporter: [["list"]],
  use: {
    baseURL: process.env.E2E_BASE_URL ?? "http://127.0.0.1:4173",
    locale: "it-IT",
    timezoneId: "Europe/Rome",
    acceptDownloads: true,
    launchOptions: executablePath ? { executablePath, args: extraArgs } : {},
    trace: "retain-on-failure",
  },
  projects: [
    { name: "desktop", use: { viewport: { width: 1280, height: 860 } } },
    { name: "mobile", use: { viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true }, testIgnore: /desktop-only/ },
  ],
});
