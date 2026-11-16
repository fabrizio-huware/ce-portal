import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

import { PRESALE, api, cleanup, createCe, expectNoPageOverflow, loginAs } from "./helpers";

test.afterEach(async ({ page }) => cleanup(page));

const PREVIEW = (page: Page) => page.getByRole("region", { name: "Anteprima dei totali" });
const ONE_LINE = [{ name: "Delivery", lines: [{ activity: "Sviluppo", profile: "Senior", hours: "16" }] }]; // 2 giorni: 1.700 € di ricavi
const LOADED = (page: Page) => expect(page.locator(".opacity-60")).toHaveCount(0); // anteprima aggiornata

async function openEditor(page: Page, id: string) {
  await loginAs(page, PRESALE);
  await page.goto(`/ce/${id}/modifica`);
  await expect(page.getByRole("heading", { name: "Fasi e righe" })).toBeVisible();
}

async function addDiscount(page: Page, n: number, description: string, value: string, kind: "amount" | "percent" = "amount") {
  await page.getByRole("button", { name: "+ Aggiungi uno sconto" }).click();
  await page.getByLabel(`Descrizione dello sconto ${n}`, { exact: true }).fill(description);
  if (kind === "percent") await page.getByLabel(`Tipo dello sconto ${n}`, { exact: true }).selectOption("percent");
  await page.getByLabel(kind === "percent" ? `Percentuale dello sconto ${n}` : `Importo dello sconto ${n}`, { exact: true }).fill(value);
}

test.describe("sconti", () => {
  test("importo e percentuale tolgono dal prezzo, i costi restano, e tutto resta dopo il salvataggio", async ({ page }) => {
    const ce = await createCe(page, { phases: ONE_LINE });
    await openEditor(page, ce.id);
    await expect(PREVIEW(page)).toContainText("1.700,00 €");
    await expect(page.getByText("Nessuno sconto.")).toBeVisible();

    await addDiscount(page, 1, "Sconto cliente storico", "200");
    await addDiscount(page, 2, "Sconto volume", "10", "percent");
    const panel = page.getByRole("region", { name: "Sconti" });
    await expect(PREVIEW(page)).toContainText("1.330,00 €"); // 1.700 - 200 - 170
    await expect(panel.getByText("370,00 €")).toBeVisible(); // totale sconti
    await expect(panel.getByText("170,00 €")).toBeVisible(); // 10% di 1.700
    await expect(PREVIEW(page)).toContainText("660,00 €"); // i costi non cambiano
    await LOADED(page);

    await page.getByRole("button", { name: "Salva" }).click();
    await expect(page.getByText("Modifiche salvate")).toBeVisible();
    await page.reload();
    await expect(page.getByLabel("Descrizione dello sconto 1", { exact: true })).toHaveValue("Sconto cliente storico");
    await expect(page.getByLabel("Tipo dello sconto 2", { exact: true })).toHaveValue("percent");
    await expect(page.getByLabel("Percentuale dello sconto 2", { exact: true })).toHaveValue("10");
    await expect(PREVIEW(page)).toContainText("1.330,00 €");

    const saved = await api(page, PRESALE, "GET", `/api/v1/ce/${ce.id}`);
    expect(saved.json.discounts.map((d: { description: string; kind: string; value: string }) => [d.description, d.kind, d.value])).toEqual([
      ["Sconto cliente storico", "amount", "200.00"],
      ["Sconto volume", "percent", "10.00"],
    ]);
    expect(saved.json.calculation.total.revenue).toBe("1330.00");
    expect(saved.json.calculation.total.cost).toBe("660.00");
  });

  test("il dettaglio mostra la sezione, la riga «Sconti» nel riepilogo", async ({ page }) => {
    const ce = await createCe(page, { phases: ONE_LINE });
    await openEditor(page, ce.id);
    await addDiscount(page, 1, "Sconto riservato", "100");
    await LOADED(page);
    await page.getByRole("button", { name: "Salva" }).click();
    await expect(page.getByText("Modifiche salvate")).toBeVisible();

    await page.goto(`/ce/${ce.id}`);
    await expect(page.getByRole("group", { name: "Sconti" })).toContainText("Sconto riservato");
    await page.getByRole("tab", { name: /Riepilogo/ }).click();
    await expect(page.getByRole("row", { name: /^Sconti/ })).toContainText("-100,00 €");
  });

  test("controlli immediati: sopra il 100% o con descrizione mancante il salvataggio è bloccato", async ({ page }) => {
    const ce = await createCe(page, { phases: ONE_LINE });
    await openEditor(page, ce.id);
    await addDiscount(page, 1, "Troppo", "150", "percent");
    await expect(page.getByLabel("Percentuale dello sconto 1", { exact: true })).toHaveAttribute("aria-invalid", "true");
    await page.getByRole("button", { name: "Salva" }).click();
    await expect(page.getByRole("alert")).toContainText("percentuale, al massimo 100");
    await page.getByLabel("Percentuale dello sconto 1", { exact: true }).fill("100");
    await expect(page.getByLabel("Percentuale dello sconto 1", { exact: true })).not.toHaveAttribute("aria-invalid", "true");
  });

  test("uno sconto oltre il prezzo è rifiutato dal server con un messaggio chiaro", async ({ page }) => {
    const ce = await createCe(page, { phases: ONE_LINE });
    await openEditor(page, ce.id);
    await addDiscount(page, 1, "Esagerato", "5000");
    await page.getByRole("button", { name: "Salva" }).click();
    await expect(page.getByRole("alert")).toContainText("supera il prezzo");
    const saved = await api(page, PRESALE, "GET", `/api/v1/ce/${ce.id}`);
    expect(saved.json.discounts).toEqual([]);
  });

  test("senza scorrimento della pagina e senza violazioni di accessibilità", async ({ page }) => {
    const ce = await createCe(page, { phases: ONE_LINE });
    await openEditor(page, ce.id);
    await addDiscount(page, 1, "Sconto", "50");
    await LOADED(page);
    await expectNoPageOverflow(page);
    const results = await new AxeBuilder({ page }).analyze();
    expect(results.violations).toEqual([]);
  });
});
