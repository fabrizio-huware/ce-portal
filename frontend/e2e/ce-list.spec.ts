import { expect, test } from "@playwright/test";

import { ADMIN, PRESALE, VIEWER, count, loginAs, openFilters } from "./helpers";

const ALL = ["PS-ALFA-ECOM-PJT", "PS-BETA-CRM-PJT", "PS-GAMMA-DATA-PJT", "PS-DELTA-APP-PJT", "PS-ALFA-AI-PJT", "PS-BETA-MIG-PJT", "PS-GAMMA-BI-PJT", "PS-DELTA-SUP-PJT"];

test.describe("elenco per admin e presale", () => {
  test.beforeEach(async ({ page }) => loginAs(page, PRESALE));

  test("mostra tutti i conti economici con codice, cliente e stato", async ({ page }) => {
    await expect(count(page)).toContainText("8 conti economici");
    for (const code of ALL) await expect(page.getByRole("link", { name: code }).first()).toBeVisible();
    const results = page.locator("tbody:visible, ul:visible"); // le voci del menu "Stato" non sono risultati
    await expect(results.getByText("Rifiutato").first()).toBeVisible();
    await expect(results.getByText("In approvazione").first()).toBeVisible();
  });

  test("filtro per stato", async ({ page }) => {
    await openFilters(page);
    await page.getByLabel("Stato").selectOption("approved");
    await expect(count(page)).toContainText("3 conti economici"); // ECOM ha una v2 in bozza: l'ultima versione non è approvata
    await expect(page).toHaveURL(/status=approved/);
    await expect(page.getByRole("link", { name: "PS-GAMMA-DATA-PJT" })).toHaveCount(0);
  });

  test("filtro per codice (con pausa di digitazione) e azzeramento", async ({ page }) => {
    await openFilters(page);
    await page.getByLabel("Codice").fill("beta");
    await expect(count(page)).toContainText("2 conti economici");
    await expect(page).toHaveURL(/code=beta/);
    await page.getByRole("button", { name: "Azzera filtri" }).click();
    await expect(count(page)).toContainText("8 conti economici");
    await expect(page.getByLabel("Codice")).toHaveValue("");
  });

  test("filtro per cliente e per progetto", async ({ page }) => {
    await openFilters(page);
    await page.getByLabel("Cliente").selectOption({ label: "Beta Banca" });
    await expect(count(page)).toContainText("2 conti economici");
    await page.getByLabel("Progetto").fill("CRM");
    await expect(count(page)).toContainText("1 conto economico");
    await expect(page.getByRole("link", { name: "PS-BETA-CRM-PJT" }).first()).toBeVisible();
  });

  test("filtro per periodo: progetti attivi nell'intervallo", async ({ page }) => {
    await openFilters(page);
    await page.getByLabel("Attivi dal").fill("2026-11-01");
    await page.getByLabel("Attivi fino al").fill("2026-12-31");
    // attivi a nov-dic 2026: GAMMA-DATA (fino al 18/12), BETA-MIG (1/9-18/12), DELTA-SUP (fino al 30/11)
    await expect(count(page)).toContainText("3 conti economici");
  });

  test("solo i miei CE", async ({ page }) => {
    await openFilters(page);
    await page.getByLabel("Solo i miei CE").check();
    await expect(count(page)).toContainText("5 conti economici"); // Anna ne ha creati 5, Paolo 3
  });

  test("nessun risultato: messaggio e possibilità di ripartire", async ({ page }) => {
    await openFilters(page);
    await page.getByLabel("Codice").fill("inesistente");
    await expect(page.getByRole("heading", { name: "Nessun risultato" })).toBeVisible();
    await page.getByRole("button", { name: "Azzera filtri" }).click();
    await expect(count(page)).toContainText("8 conti economici");
  });

  test("i filtri restano dopo il ricaricamento e si possono condividere con l'indirizzo", async ({ page }) => {
    await page.goto("/ce?status=submitted");
    await expect(count(page)).toContainText("1 conto economico");
    await page.reload();
    await expect(count(page)).toContainText("1 conto economico");
    await openFilters(page);
    await expect(page.getByLabel("Stato")).toHaveValue("submitted");
  });

  test("esporta l'elenco in Excel e CSV", async ({ page }) => {
    for (const [label, ext] of [["Excel (.xlsx)", "xlsx"], ["CSV per Excel", "csv"]]) {
      await page.getByRole("button", { name: /Esporta elenco/ }).click();
      const download = page.waitForEvent("download");
      await page.getByRole("menuitem", { name: label }).click();
      const file = await download;
      expect(file.suggestedFilename()).toMatch(new RegExp(`^elenco_ce_\\d{8}\\.${ext}$`));
      await expect(page.getByText("File scaricato")).toBeVisible();
    }
  });

  test("l'elenco esportato rispetta i filtri attivi", async ({ page }) => {
    await page.goto("/ce?status=rejected");
    await expect(count(page)).toContainText("1 conto economico");
    await page.getByRole("button", { name: /Esporta elenco/ }).click();
    const download = page.waitForEvent("download");
    await page.getByRole("menuitem", { name: "CSV per Excel" }).click();
    const path = await (await download).path();
    const text = (await import("node:fs")).readFileSync(path, "utf-8");
    expect(text).toContain("PS-ALFA-AI-PJT");
    expect(text).not.toContain("PS-BETA-CRM-PJT");
  });

  test("anche l'amministratore vede lo stesso elenco", async ({ page }) => {
    await page.evaluate(() => sessionStorage.clear()); // esce dalla sessione di Anna
    await loginAs(page, ADMIN);
    await expect(count(page)).toContainText("8 conti economici");
  });
});

test.describe("elenco per il viewer", () => {
  test.beforeEach(async ({ page }) => loginAs(page, VIEWER));

  test("vede solo i CE approvati, con le colonne ridotte", async ({ page }) => {
    await expect(count(page)).toContainText("4 conti economici"); // approvati: ECOM (v1), CRM, BI, SUP
    await expect(page.getByRole("link", { name: "PS-ALFA-ECOM-PJT" }).first()).toBeVisible();
    await expect(page.getByRole("link", { name: "PS-GAMMA-DATA-PJT" })).toHaveCount(0);
    await expect(page.getByRole("link", { name: "PS-BETA-MIG-PJT" })).toHaveCount(0);
    if (await page.getByRole("table").isVisible()) {
      const headers = await page.getByRole("columnheader").allInnerTexts();
      expect(headers.join("|")).not.toMatch(/margine|autore|stato/i);
      expect(headers.join("|")).toMatch(/prezzo/i);
    }
  });

  test("non ha i filtri riservati agli editor", async ({ page }) => {
    await openFilters(page);
    await expect(page.getByLabel("Stato")).toHaveCount(0);
    await expect(page.getByLabel("Solo i miei CE")).toHaveCount(0);
  });

  test("esporta l'elenco ridotto", async ({ page }) => {
    await page.getByRole("button", { name: /Esporta elenco/ }).click();
    const download = page.waitForEvent("download");
    await page.getByRole("menuitem", { name: "CSV per Excel" }).click();
    const file = await download;
    expect(file.suggestedFilename()).toMatch(/^elenco_ce_approvati_\d{8}\.csv$/);
    const text = (await import("node:fs")).readFileSync(await file.path(), "utf-8");
    expect(text).toContain("PS-ALFA-ECOM-PJT");
    expect(text).not.toMatch(/Margine|Costo/);
  });
});
