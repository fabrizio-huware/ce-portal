import { expect, test, type Page } from "@playwright/test";

import { PRESALE, cleanup, createCe, loginAs } from "./helpers";

test.afterEach(async ({ page }) => cleanup(page));

const PHASES = [
  { name: "Analisi", contingency: "10", lines: [{ activity: "Requisiti", profile: "Senior", hours: "40" }, { activity: "Disegno", profile: "Senior", hours: "32" }] },
  { name: "Sviluppo", lines: [{ activity: "Moduli", profile: "Senior", hours: "80" }] },
];

async function seed(page: Page) {
  const ce = await createCe(page, { phases: PHASES });
  await loginAs(page, PRESALE);
  return ce;
}

test.describe("fasi comprimibili: dettaglio", () => {
  test("una fase chiusa mostra solo intestazione e totali, anche con contingency", async ({ page }) => {
    const ce = await seed(page);
    await page.goto(`/ce/${ce.id}`);
    const analisi = page.getByRole("group", { name: "Fase Analisi" });
    await expect(analisi.getByText("Requisiti")).toBeVisible();
    await analisi.getByRole("button", { name: "Comprimi la fase Analisi" }).click();
    await expect(analisi.getByText("Requisiti")).toHaveCount(0);
    await expect(analisi.getByRole("button", { name: "Espandi la fase Analisi" })).toHaveAttribute("aria-expanded", "false");
    const totals = analisi.getByLabel("Totali della fase");
    await expect(totals).toContainText("72,00"); // ore
    await expect(totals).toContainText("con cont."); // giorni e ricavo con contingency
    await expect(page.getByRole("group", { name: "Fase Sviluppo" }).getByText("Moduli")).toBeVisible(); // l'altra resta aperta
    await analisi.getByRole("button", { name: "Espandi la fase Analisi" }).click();
    await expect(analisi.getByText("Requisiti")).toBeVisible();
  });

  test("comprimi tutte ed espandi tutte", async ({ page }) => {
    const ce = await seed(page);
    await page.goto(`/ce/${ce.id}`);
    await page.getByRole("button", { name: "Comprimi tutte" }).click();
    await expect(page.getByText("Requisiti")).toHaveCount(0);
    await expect(page.getByText("Moduli")).toHaveCount(0);
    await expect(page.getByLabel("Totali della fase")).toHaveCount(2);
    await page.getByRole("button", { name: "Espandi tutte" }).click();
    await expect(page.getByText("Requisiti")).toBeVisible();
    await expect(page.getByText("Moduli")).toBeVisible();
  });
});

test.describe("fasi comprimibili: editor", () => {
  test("chiudendo una fase i dati restano nella bozza", async ({ page }) => {
    const ce = await seed(page);
    await page.goto(`/ce/${ce.id}/modifica`);
    const hours = page.getByLabel("Ore 1 della fase Analisi", { exact: true });
    await hours.fill("48");
    await page.getByRole("button", { name: "Comprimi la fase Analisi" }).click();
    await expect(hours).toHaveCount(0);
    await expect(page.getByRole("region", { name: "Fase 1" }).getByLabel("Totali della fase")).toBeVisible();
    await page.getByRole("button", { name: "Espandi la fase Analisi" }).click();
    await expect(hours).toHaveValue("48"); // la bozza non è cambiata
  });

  test("un errore in una fase chiusa si vede, e il salvataggio la riapre", async ({ page }) => {
    const ce = await seed(page);
    await page.goto(`/ce/${ce.id}/modifica`);
    await page.getByLabel("Attività 1 della fase Analisi", { exact: true }).fill("");
    await page.getByRole("button", { name: "Comprimi tutte" }).click();
    await expect(page.getByRole("alert").filter({ hasText: "1 campo da correggere" })).toBeVisible();
    await page.getByRole("button", { name: "Salva" }).click();
    await expect(page.getByLabel("Attività 1 della fase Analisi", { exact: true })).toBeVisible(); // riaperta
    await expect(page.getByRole("button", { name: "Espandi la fase Sviluppo" })).toBeVisible(); // quella senza errori resta chiusa
  });
});
