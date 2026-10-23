import { expect, test, type Page } from "@playwright/test";

import { ADMIN, PRESALE, api, cleanup, createCe, loginAs } from "./helpers";

const PAOLO = "paolo.presale@huware.com"; // presale di Cloud & Infrastructure
const MARTA = "marta.responsabile@huware.com"; // responsabile di Data & AI
const LINE = [{ name: "Delivery", lines: [{ activity: "Sviluppo", profile: "Senior", hours: "16" }] }];

async function switchTo(page: Page, enabled: boolean) {
  const r = await api(page, ADMIN, "PUT", "/api/v1/business-units/visibility", { enabled });
  expect(r.status, JSON.stringify(r.json)).toBe(200);
}
const codesFor = async (page: Page, email: string) =>
  ((await api(page, email, "GET", "/api/v1/ce?limit=200")).json.items as { code: string }[]).map((i) => i.code);
const switchUser = async (page: Page, email: string) => { await page.evaluate(() => sessionStorage.clear()); await loginAs(page, email); };

// qualunque cosa succeda, l'interruttore torna spento: gli altri test contano su «tutti vedono tutto»
test.afterEach(async ({ page }) => { await switchTo(page, false); await cleanup(page); });

test.describe("visibilità per business unit", () => {
  test("acceso: un presale non vede i CE di un'altra business unit, spento li rivede", async ({ page }) => {
    const cloudOnly = await createCe(page, { by: PAOLO, units: ["Cloud & Infrastructure"], phases: LINE });
    await switchTo(page, true);
    await loginAs(page, PRESALE); // Anna: Data & AI
    expect(await codesFor(page, PRESALE)).not.toContain(cloudOnly.code);
    await page.goto(`/ce?q=${cloudOnly.code}`);
    await page.waitForLoadState("networkidle");
    await expect(page.getByText(cloudOnly.code)).toHaveCount(0); // nemmeno cercandolo
    await page.goto(`/ce/${cloudOnly.id}`);
    await expect(page.getByText("CE non trovato")).toBeVisible(); // come un CE che non esiste
    await switchUser(page, PAOLO); // l'autore lo vede
    await page.goto(`/ce?q=${cloudOnly.code}`);
    await expect(page.getByText(cloudOnly.code).locator("visible=true").first()).toBeVisible();
    await switchTo(page, false);
    await switchUser(page, PRESALE);
    await page.goto(`/ce/${cloudOnly.id}`);
    await expect(page.getByText(cloudOnly.code).first()).toBeVisible(); // spento: come prima
  });

  test("acceso: si vedono i CE che coinvolgono la propria business unit e quelli che si sono creati", async ({ page }) => {
    const shared = await createCe(page, { by: PAOLO, units: ["Data & AI"], phases: LINE }); // di Cloud, ma coinvolge Data & AI
    const own = await createCe(page, { units: ["Digital Experience"], phases: LINE }); // di Anna, anche se la sua unit non c'è
    const hidden = await createCe(page, { by: PAOLO, units: ["Cloud & Infrastructure"], phases: LINE });
    await switchTo(page, true);
    const seen = await codesFor(page, PRESALE);
    expect(seen).toContain(shared.code);
    expect(seen).toContain(own.code);
    expect(seen).not.toContain(hidden.code);
    await loginAs(page, PRESALE);
    await page.goto("/ce?q=PS-E2E");
    await expect(page.getByText(shared.code).locator("visible=true").first()).toBeVisible();
    await expect(page.getByText(own.code).locator("visible=true").first()).toBeVisible();
    await expect(page.getByText(hidden.code)).toHaveCount(0);
  });

  test("il responsabile della business unit coinvolta approva un CE in approvazione", async ({ page }) => {
    const ce = await createCe(page, { units: ["Data & AI"], phases: LINE }); // di Anna
    expect((await api(page, PRESALE, "POST", `/api/v1/ce/${ce.id}/submit`)).status).toBe(200);
    await switchTo(page, true);
    await loginAs(page, MARTA);
    await page.goto(`/ce/${ce.id}`);
    await expect(page.getByRole("button", { name: "Rifiuta", exact: true })).toBeVisible();
    await page.getByRole("button", { name: "Approva", exact: true }).click();
    await page.getByRole("dialog").getByRole("button", { name: "Approva" }).click();
    await expect(page.locator("main").getByText("Approvato", { exact: true }).first()).toBeVisible();
  });

  test("il responsabile di un'altra business unit non vede nemmeno il CE", async ({ page }) => {
    const ce = await createCe(page, { by: PAOLO, units: ["Cloud & Infrastructure"], phases: LINE });
    expect((await api(page, PAOLO, "POST", `/api/v1/ce/${ce.id}/submit`)).status).toBe(200);
    await switchTo(page, true);
    await loginAs(page, MARTA); // Data & AI
    await page.goto(`/ce/${ce.id}`);
    await expect(page.getByText("CE non trovato")).toBeVisible();
    await expect(page.getByRole("button", { name: "Approva", exact: true })).toHaveCount(0);
  });
});
