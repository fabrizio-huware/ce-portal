import { expect, test, type Page } from "@playwright/test";

import { ADMIN, api, loginAs } from "./helpers";

const TO = 2098; // anno lontano: il listino è condiviso con gli altri test, e la pagina si apre sull'ultimo anno con tariffe

/** Toglie le tariffe dell'anno di prova da tutti i profili, qualunque sia l'esito del test. */
async function removeRates(page: Page) {
  const profiles = (await api(page, ADMIN, "GET", "/api/v1/profiles")).json as { id: string; rates: { year: number }[] }[];
  for (const p of profiles) if (p.rates.some((r) => r.year === TO)) await api(page, ADMIN, "DELETE", `/api/v1/profiles/${p.id}/rates/${TO}`);
}

test.afterEach(async ({ page }) => { await removeRates(page); });

test.describe("copia delle tariffe su altri anni", () => {
  test("anteprima senza scrivere, poi conferma con un adeguamento; una seconda copia sovrascrive", async ({ page }) => {
    await loginAs(page, ADMIN);
    await removeRates(page);
    await page.goto("/admin/listino?anno=2026");
    await page.getByRole("button", { name: "Copia le tariffe del 2026 su altri anni" }).click();
    const dlg = page.getByRole("dialog");
    await expect(dlg.getByRole("button", { name: "Mostra l'anteprima" })).toBeDisabled();

    await dlg.getByLabel("Anni di arrivo").fill("2026");
    await expect(dlg.getByText("non può essere quello di partenza")).toBeVisible();
    await dlg.getByLabel("Anni di arrivo").fill(String(TO));
    await dlg.getByLabel("Adeguamento del prezzo (%)").fill("abc");
    await expect(dlg.getByText("Inserisci un numero")).toBeVisible();
    await dlg.getByLabel("Adeguamento del prezzo (%)").fill("10");
    await dlg.getByLabel("Adeguamento del costo (%)").fill("-10");
    await dlg.getByRole("button", { name: "Mostra l'anteprima" }).click();

    const preview = dlg.getByRole("region", { name: "Anteprima", exact: true });
    await expect(preview).toContainText("nulla è stato scritto");
    await expect(preview.getByRole("row").filter({ has: page.getByRole("rowheader", { name: "Senior" }) })).toContainText("935,00 €"); // 850 +10%
    await expect(preview.getByRole("row").filter({ has: page.getByRole("rowheader", { name: "Senior" }) })).toContainText("297,00 €"); // 330 -10%
    let list = (await api(page, ADMIN, "GET", "/api/v1/profiles")).json as { rates: { year: number }[] }[];
    expect(list.some((p) => p.rates.some((r) => r.year === TO))).toBe(false); // l'anteprima non scrive

    await dlg.getByLabel("Anni di arrivo").fill(`${TO}`); // cambiare un campo toglie l'anteprima: va rivista
    await dlg.getByLabel("Adeguamento del prezzo (%)").fill("10,5");
    await expect(preview).toHaveCount(0);
    await dlg.getByRole("button", { name: "Mostra l'anteprima" }).click();
    await expect(preview.getByRole("row").filter({ has: page.getByRole("rowheader", { name: "Senior" }) })).toContainText("939,25 €"); // 850 +10,5%
    await dlg.getByRole("button", { name: "Conferma e copia" }).click();
    await expect(page.getByRole("status").filter({ hasText: `Tariffe 2026 copiate su ${TO}` })).toBeVisible();

    list = (await api(page, ADMIN, "GET", "/api/v1/profiles")).json as { name: string; rates: { year: number; daily_price: string; daily_cost: string }[] }[];
    const senior = (list as unknown as { name: string; rates: { year: number; daily_price: string; daily_cost: string }[] }[]).find((p) => p.name === "Senior")!;
    expect(senior.rates.find((r) => r.year === TO)).toMatchObject({ daily_price: "939.25", daily_cost: "297.00" });
    expect(senior.rates.find((r) => r.year === 2026)).toMatchObject({ daily_price: "850.00", daily_cost: "330.00" }); // l'anno di partenza non cambia

    // una seconda copia sovrascrive: l'anteprima lo dice e mostra il vecchio valore
    await page.getByRole("button", { name: "Copia le tariffe del 2026 su altri anni" }).click();
    await dlg.getByLabel("Anni di arrivo").fill(String(TO));
    await dlg.getByRole("button", { name: "Mostra l'anteprima" }).click();
    await expect(dlg.getByRole("region", { name: "Anteprima", exact: true })).toContainText("sovrascritta");
    await dlg.getByRole("button", { name: "Annulla" }).click();
    await expect(dlg).toHaveCount(0);
  });
});
