import { expect, test } from "@playwright/test";

import { PRESALE, VIEWER, expectNoPageOverflow, loginAs } from "./helpers";

test.describe("schermo piccolo (smartphone)", () => {
  test.skip(({ isMobile }) => !isMobile, "solo smartphone");

  test("l'elenco diventa una lista di schede e la pagina non scorre in orizzontale", async ({ page }) => {
    await loginAs(page, PRESALE);
    await expect(page.getByRole("table")).toBeHidden();
    await expect(page.getByRole("link", { name: /PS-ALFA-ECOM-PJT/ }).first()).toBeVisible();
    await expectNoPageOverflow(page);
  });

  test("i filtri stanno dietro al pulsante e il menu si apre", async ({ page }) => {
    await loginAs(page, PRESALE);
    await expect(page.getByLabel("Codice")).toBeHidden();
    await page.getByRole("button", { name: /^Filtri/ }).click();
    await expect(page.getByLabel("Codice")).toBeVisible();
    await page.getByRole("button", { name: "Menu" }).click();
    await expect(page.getByRole("navigation", { name: "Principale mobile" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Esci" })).toBeVisible();
  });

  test("il dettaglio non fa scorrere la pagina; le tabelle larghe scorrono al loro interno", async ({ page }) => {
    await loginAs(page, PRESALE);
    await page.getByRole("link", { name: /PS-ALFA-ECOM-PJT/ }).first().click();
    await expect(page.getByRole("heading", { name: "PS-ALFA-ECOM-PJT", level: 1 })).toBeVisible();
    await expectNoPageOverflow(page);
    for (const name of ["Riepilogo", "Staffing mensile", "Versioni", "Storico"]) {
      await page.getByRole("tab", { name }).click();
      await expectNoPageOverflow(page);
    }
  });

  test("anche la vista del viewer si legge bene", async ({ page }) => {
    await loginAs(page, VIEWER);
    await page.getByRole("link", { name: /PS-ALFA-ECOM-PJT/ }).first().click();
    await expect(page.getByText("Totale generale")).toBeVisible();
    await expectNoPageOverflow(page);
  });

  test("i bersagli da toccare sono abbastanza grandi", async ({ page }) => {
    await loginAs(page, PRESALE);
    const menu = await page.getByRole("button", { name: "Menu" }).boundingBox();
    expect(menu!.width).toBeGreaterThanOrEqual(40);
    expect(menu!.height).toBeGreaterThanOrEqual(40);
  });
});
