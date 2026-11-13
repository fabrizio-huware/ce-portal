import { expect, test, type Page } from "@playwright/test";

import { ADMIN, PRESALE, api, cleanup, createCe, loginAs } from "./helpers";

test.afterEach(async ({ page }) => cleanup(page));

async function ceWithMenu(page: Page) {
  const ce = await createCe(page, { phases: [{ name: "Delivery", lines: [{ activity: "Sviluppo", profile: "Senior", hours: "16" }] }] });
  await loginAs(page, PRESALE);
  await page.goto(`/ce/${ce.id}`);
  await page.getByRole("button", { name: /^Esporta/ }).click();
  return ce;
}

/** Le email che il portale ha preparato per il CE, lette dalle notifiche (solo admin). */
async function reports(page: Page, code: string) {
  const res = await api(page, ADMIN, "GET", `/api/v1/notifications?type=ce_report&limit=50`);
  return (res.json.items as { subject: string; recipient: string; status: string }[]).filter((n) => n.subject?.includes(code));
}

test.describe("invio del report per email", () => {
  test("il menu Esporta ha la nuova voce dopo i riepiloghi", async ({ page }) => {
    await ceWithMenu(page);
    const items = await page.getByRole("menuitem").allInnerTexts();
    expect(items.at(-1)).toContain("Invia per email");
    expect(items.some((t) => t.startsWith("Riepilogo Excel"))).toBe(true);
  });

  test("si invia il riepilogo PDF a un indirizzo esterno e compare la conferma", async ({ page }) => {
    const ce = await ceWithMenu(page);
    await page.getByRole("menuitem", { name: /Invia per email/ }).click();
    const dialog = page.getByRole("dialog");
    await expect(dialog.getByLabel(/Riepilogo PDF/)).toBeChecked();
    await expect(dialog.getByRole("button", { name: "Invia" })).toBeDisabled();
    await dialog.getByLabel("Indirizzo del destinatario").fill("mario.rossi@cliente.it");
    await dialog.getByLabel(/Messaggio/).fill("Ecco il riepilogo concordato");
    await dialog.getByRole("button", { name: "Invia" }).click();
    await expect(dialog.getByRole("status")).toContainText("mario.rossi@cliente.it");
    await dialog.getByRole("button", { name: "Chiudi" }).click();
    await expect(dialog).toHaveCount(0);
    const sent = await reports(page, ce.code);
    expect(sent).toHaveLength(1);
    expect(sent[0]).toMatchObject({ recipient: "mario.rossi@cliente.it", status: "sent" });
  });

  test("il report completo a un esterno viene rifiutato e si passa al riepilogo", async ({ page }) => {
    const ce = await ceWithMenu(page);
    await page.getByRole("menuitem", { name: /Invia per email/ }).click();
    const dialog = page.getByRole("dialog");
    await dialog.getByLabel(/PDF completo/).check();
    await expect(dialog.getByRole("status")).toContainText("solo a indirizzi aziendali");
    await dialog.getByLabel("Indirizzo del destinatario").fill("mario.rossi@cliente.it");
    await dialog.getByRole("button", { name: "Invia" }).click();
    await expect(dialog.getByRole("alert")).toContainText("costi e margini");
    expect(await reports(page, ce.code)).toHaveLength(0); // nulla è partito
    await dialog.getByRole("button", { name: "Passa al riepilogo" }).click();
    await expect(dialog.getByLabel(/Riepilogo PDF/)).toBeChecked();
    await dialog.getByRole("button", { name: "Invia" }).click();
    await expect(dialog.getByRole("status")).toContainText("è stato inviato");
    expect(await reports(page, ce.code)).toHaveLength(1);
  });

  test("il report completo a un collega parte", async ({ page }) => {
    const ce = await ceWithMenu(page);
    await page.getByRole("menuitem", { name: /Invia per email/ }).click();
    const dialog = page.getByRole("dialog");
    await dialog.getByLabel(/Excel completo/).check();
    await dialog.getByLabel("Indirizzo del destinatario").fill("collega@huware.com");
    await dialog.getByRole("button", { name: "Invia" }).click();
    await expect(dialog.getByRole("status")).toContainText("è stato inviato");
    expect((await reports(page, ce.code))[0].subject).toContain("Excel completo");
  });

  test("Annulla chiude senza inviare nulla", async ({ page }) => {
    const ce = await ceWithMenu(page);
    await page.getByRole("menuitem", { name: /Invia per email/ }).click();
    const dialog = page.getByRole("dialog");
    await dialog.getByLabel("Indirizzo del destinatario").fill("mario.rossi@cliente.it");
    await dialog.getByRole("button", { name: "Annulla" }).click();
    await expect(dialog).toHaveCount(0);
    expect(await reports(page, ce.code)).toHaveLength(0);
  });
});
