import { expect, type Page } from "@playwright/test";

export const ADMIN = "admin@huware.com";
export const PRESALE = "anna.presale@huware.com";
export const VIEWER = "vera.viewer@huware.com";

/** Accesso con il login simulato del backend locale. */
export async function loginAs(page: Page, email: string) {
  await page.goto("/login");
  await page.getByLabel("Email di un utente registrato").fill(email);
  await page.getByRole("button", { name: "Entra senza Google" }).click();
  await expect(page).toHaveURL(/\/ce$/);
}

export async function isMobile(page: Page) {
  return (page.viewportSize()?.width ?? 1280) < 768;
}

/** Nessuna barra di scorrimento orizzontale sulla pagina. */
export async function expectNoPageOverflow(page: Page) {
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow, "la pagina non deve scorrere in orizzontale").toBeLessThanOrEqual(1);
}

/** Chiamata diretta alle API con il token di un utente (per preparare o verificare dati). */
export async function apiGet(page: Page, email: string, path: string) {
  const login = await page.request.post("/api/v1/auth/dev-login", { data: { email } });
  const token = (await login.json()).access_token;
  const response = await page.request.get(path, { headers: { Authorization: `Bearer ${token}` } });
  return { status: response.status(), json: await response.json() };
}

/** Su schermi stretti i filtri stanno dietro al pulsante "Filtri". */
export async function openFilters(page: Page) {
  const button = page.getByRole("button", { name: /^Filtri/ });
  if (await button.isVisible()) {
    if ((await button.getAttribute("aria-expanded")) !== "true") await button.click();
  }
}

export function count(page: Page) {
  return page.locator('[aria-live="polite"]');
}
