import { expect, test, type Page } from "@playwright/test";

import { ADMIN, PRESALE, VIEWER, api, cleanup, createCe, loginAs, openFilters } from "./helpers";

test.afterEach(async ({ page }) => cleanup(page));

/** Un CE approvato (l'autore è Anna), pronto per l'esito. */
async function approvedCe(page: Page) {
  const ce = await createCe(page, { phases: [{ name: "Delivery", lines: [{ activity: "Sviluppo", profile: "Senior", hours: "16" }] }] });
  expect((await api(page, PRESALE, "POST", `/api/v1/ce/${ce.id}/submit`)).status).toBe(200);
  expect((await api(page, ADMIN, "POST", `/api/v1/ce/${ce.id}/approve`)).status).toBe(200);
  return ce;
}

const setOutcome = (page: Page, id: string, outcome: "won" | "lost" | null, note?: string) =>
  api(page, PRESALE, "PUT", `/api/v1/ce/${id}/outcome`, { outcome, ...(note ? { note } : {}) });

test.describe("esito della trattativa", () => {
  test("l'autore segna Close Won con una nota: si vede nel dettaglio, nell'elenco e nel filtro", async ({ page }) => {
    const ce = await approvedCe(page);
    await loginAs(page, PRESALE);
    await page.goto(`/ce/${ce.id}`);
    await page.getByRole("button", { name: "Segna l'esito" }).click();
    const dialog = page.getByRole("dialog");
    const save = dialog.getByRole("button", { name: "Salva l'esito" });
    await expect(save).toBeDisabled(); // nulla è cambiato
    await dialog.getByLabel("Close Won").check();
    await dialog.getByLabel("Nota (facoltativa)").fill("Contratto quadro firmato");
    await save.click();
    await expect(dialog).toHaveCount(0);
    await expect(page.getByText("Close Won").first()).toBeVisible();
    await expect(page.getByText("Contratto quadro firmato")).toBeVisible();
    await expect(page.getByRole("button", { name: "Cambia l'esito" })).toBeVisible();

    await page.goto(`/ce?code=${ce.code}&bu=tutte`);
    await expect(page.getByText("Close Won").locator("visible=true").first()).toBeVisible(); // nell'elenco
    await page.goto(`/ce?code=${ce.code}&bu=tutte&esito=lost`);
    await expect(page.getByRole("heading", { name: "Nessun risultato" })).toBeVisible(); // il filtro «Esito»
    await page.goto(`/ce?code=${ce.code}&bu=tutte&esito=won`);
    await openFilters(page);
    await expect(page.getByLabel("Esito", { exact: true }).locator("option:checked")).toHaveText("Close Won");
    await expect(page.getByText(ce.code).locator("visible=true").first()).toBeVisible();
  });

  test("si cambia e si toglie l'esito", async ({ page }) => {
    const ce = await approvedCe(page);
    await setOutcome(page, ce.id, "won");
    await loginAs(page, PRESALE);
    await page.goto(`/ce/${ce.id}`);
    await page.getByRole("button", { name: "Cambia l'esito" }).click();
    await page.getByRole("dialog").getByLabel("Close Lost").check();
    await page.getByRole("dialog").getByLabel("Motivo (facoltativo)").fill("Ha scelto un concorrente");
    await page.getByRole("dialog").getByRole("button", { name: "Salva l'esito" }).click();
    await expect(page.getByText("Close Lost").first()).toBeVisible();
    await page.getByRole("button", { name: "Cambia l'esito" }).click();
    await page.getByRole("dialog").getByLabel("Nessun esito").check();
    await page.getByRole("dialog").getByRole("button", { name: "Salva l'esito" }).click();
    await expect(page.getByRole("button", { name: "Segna l'esito" })).toBeVisible();
    await expect(page.getByText("Close Lost")).toHaveCount(0);
  });

  test("Close Lost: niente nuova versione, e l'amministratore vede perché non può eliminare", async ({ page }) => {
    const ce = await approvedCe(page);
    await setOutcome(page, ce.id, "lost", "Prezzo");
    await loginAs(page, ADMIN);
    await page.goto(`/ce/${ce.id}`);
    await expect(page.getByText("Il CE ha l'esito «Close Lost»: toglilo prima di eliminarlo")).toBeVisible(); // la segnalazione
    await expect(page.getByRole("button", { name: "Nuova versione" })).toHaveCount(0);
    await page.getByRole("button", { name: "Altre azioni" }).click();
    await expect(page.getByRole("menuitem", { name: "Elimina il CE" })).toHaveCount(0);
    expect((await api(page, ADMIN, "DELETE", `/api/v1/ce/${ce.id}`)).status).toBe(409);
  });

  test("un CE non approvato non ha il pulsante dell'esito", async ({ page }) => {
    const ce = await createCe(page, {});
    await loginAs(page, PRESALE);
    await page.goto(`/ce/${ce.id}`);
    await expect(page.getByRole("button", { name: /l'esito/ })).toHaveCount(0);
    expect((await setOutcome(page, ce.id, "won")).status).toBe(409);
  });
});

test.describe("esito: viewer", () => {
  test("il viewer vede l'etichetta dell'esito, non la nota", async ({ page }) => {
    const ce = await approvedCe(page);
    await setOutcome(page, ce.id, "lost", "Segreto del motivo");
    await loginAs(page, VIEWER);
    await page.goto(`/ce?code=${ce.code}`);
    await expect(page.getByText("Close Lost").locator("visible=true").first()).toBeVisible();
    await page.goto(`/ce/${ce.id}`);
    await expect(page.getByText("Close Lost").first()).toBeVisible();
    await expect(page.getByText("Segreto del motivo")).toHaveCount(0);
  });
});
