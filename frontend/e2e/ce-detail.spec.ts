import { expect, test } from "@playwright/test";

import { PRESALE, VIEWER, apiGet, loginAs } from "./helpers";

async function open(page: import("@playwright/test").Page, code: string) {
  await page.getByRole("link", { name: code }).first().click();
  await expect(page.getByRole("heading", { name: code, level: 1 })).toBeVisible();
}
const tab = (page: import("@playwright/test").Page, name: string) => page.getByRole("tab", { name });

test.describe("dettaglio per admin e presale", () => {
  test.beforeEach(async ({ page }) => loginAs(page, PRESALE));

  test("mostra testata, stato, versione e indicatori", async ({ page }) => {
    await open(page, "PS-ALFA-ECOM-PJT");
    await expect(page.getByText("Piattaforma e-commerce")).toBeVisible();
    await expect(page.getByText("Bozza").first()).toBeVisible();          // l'ultima versione (v2) è una bozza
    await expect(page.getByText("v2 di 2")).toBeVisible();
    await expect(page.getByText("Prezzo progetto")).toBeVisible();
    await expect(page.getByText(/€/).first()).toBeVisible();
    for (const label of ["Margine", "Costi", "Prezzo minimo", "Giornate", "Fee media minima"]) await expect(page.getByText(label, { exact: true }).first()).toBeVisible();
  });

  test("il dettaglio elenca fasi e righe, con contingency, collaboratori ed esterni", async ({ page }) => {
    await open(page, "PS-ALFA-ECOM-PJT");
    await expect(page.getByRole("group", { name: "Fase Delivery" })).toBeVisible();
    await expect(page.getByText("Contingency 10,00%")).toBeVisible();
    await expect(page.getByText("Sviluppo catalogo")).toBeVisible();
    await expect(page.getByText("Luca Ferri").first()).toBeVisible();
    await expect(page.getByText("esterno").first()).toBeVisible();
    await expect(page.getByText("PM", { exact: true }).first()).toBeVisible();
    await expect(page.getByText("Totale Delivery")).toBeVisible();
    await expect(page.getByText("Ricavo da contingency (senza costi)")).toBeVisible();
  });

  test("riepilogo per servizi e per profilo", async ({ page }) => {
    await open(page, "PS-ALFA-ECOM-PJT");
    await tab(page, "Riepilogo").click();
    await expect(page.getByRole("cell", { name: "Servizi esterni" })).toBeVisible();
    await expect(page.getByRole("cell", { name: "Totale", exact: true })).toBeVisible();
    await expect(page.getByRole("cell", { name: /Specialist/ }).first()).toBeVisible();
  });

  test("staffing mensile con FTE", async ({ page }) => {
    await open(page, "PS-ALFA-ECOM-PJT");
    await tab(page, "Staffing mensile").click();
    for (const m of ["gen 2026", "feb 2026", "mar 2026", "apr 2026", "mag 2026", "giu 2026"]) await expect(page.getByRole("cell", { name: m })).toBeVisible();
    await expect(page.getByText("FTE = giorni")).toBeVisible();
  });

  test("versioni: si può aprire una versione precedente e si capisce che non è l'ultima", async ({ page }) => {
    await open(page, "PS-ALFA-ECOM-PJT");
    await tab(page, "Versioni").click();
    await expect(page.getByRole("link", { name: "Versione 1" })).toBeVisible();
    await expect(page.getByRole("link", { name: "Versione 2" })).toBeVisible();
    await page.getByRole("link", { name: "Versione 1" }).click();
    await expect(page).toHaveURL(/\?v=1$/);
    await expect(page.getByText("Stai guardando la versione 1")).toBeVisible();
    await expect(page.getByText("Approvato").first()).toBeVisible();
    await page.getByRole("link", { name: "Vai all'ultima versione" }).click();
    await expect(page.getByText("v2 di 2")).toBeVisible();
  });

  test("storico delle attività", async ({ page }) => {
    await open(page, "PS-ALFA-ECOM-PJT");
    await tab(page, "Storico").click();
    for (const action of ["Creato", "Salvato", "Inviato in approvazione", "Approvato", "Nuova versione"]) {
      await expect(page.getByText(action, { exact: true }).first()).toBeVisible();
    }
  });

  test("un CE rifiutato mostra chi lo ha rifiutato e perché", async ({ page }) => {
    await open(page, "PS-ALFA-AI-PJT");
    await expect(page.getByRole("alert")).toContainText("Mancano le ore di test e il piano di rilascio");
    await expect(page.getByText("Rifiutato").first()).toBeVisible();
  });

  test("un CE in modalità percentuali mostra le righe con ore e giorni calcolati", async ({ page }) => {
    await open(page, "PS-DELTA-APP-PJT");
    await expect(page.getByText("Percentuali", { exact: true })).toBeVisible();
    await expect(page.getByText("Sviluppo app")).toBeVisible();
    await expect(page.getByText("Elena Marino").first()).toBeVisible();
  });

  test("esportazioni del CE: Excel, PDF, CSV e riepilogo senza costi", async ({ page }) => {
    await open(page, "PS-ALFA-ECOM-PJT");
    const cases: [string, RegExp][] = [
      ["Excel completo", /^PS-ALFA-ECOM-PJT_v2\.xlsx$/], ["PDF completo", /^PS-ALFA-ECOM-PJT_v2\.pdf$/],
      ["CSV delle righe", /^PS-ALFA-ECOM-PJT_v2\.csv$/], ["Riepilogo PDF", /^PS-ALFA-ECOM-PJT_v2_riepilogo\.pdf$/],
    ];
    for (const [label, name] of cases) {
      await page.getByRole("button", { name: /^Esporta/ }).click();
      const download = page.waitForEvent("download");
      await page.getByRole("menuitem", { name: label }).click();
      const file = await download;
      expect(file.suggestedFilename()).toMatch(name);
      const bytes = (await import("node:fs")).readFileSync(await file.path());
      expect(bytes.length).toBeGreaterThan(400);
      if (label.includes("PDF")) expect(bytes.subarray(0, 4).toString()).toBe("%PDF");
      if (label.includes("Excel")) expect(bytes.subarray(0, 2).toString()).toBe("PK");
    }
  });

  test("un CE inesistente mostra un errore comprensibile", async ({ page }) => {
    await page.goto("/ce/00000000-0000-0000-0000-000000000000");
    await expect(page.getByRole("alert")).toContainText("non trovato");
    await expect(page.getByRole("link", { name: /Tutti i conti economici/ })).toBeVisible();
  });
});

test.describe("dettaglio per il viewer", () => {
  test.beforeEach(async ({ page }) => loginAs(page, VIEWER));

  test("mostra solo giornate e ricavi per fase, mai costi o margini", async ({ page }) => {
    await open(page, "PS-ALFA-ECOM-PJT");
    await expect(page.getByRole("region", { name: "Giornate" })).toContainText("Management");
    await expect(page.getByRole("region", { name: "Giornate" })).toContainText("Delivery");
    await expect(page.getByRole("region", { name: "Ricavi per fase" })).toBeVisible();
    await expect(page.getByText("Totale generale")).toBeVisible();
    await expect(page.getByText("Approvato").first()).toBeVisible();
    const body = await page.locator("body").innerText();
    for (const forbidden of ["Costi", "Costo", "Margine", "Fee media", "Specialist", "Sviluppo catalogo", "Collaboratore", "Contingency"]) {
      expect(body, `il viewer non deve vedere "${forbidden}"`).not.toContain(forbidden);
    }
    await expect(page.getByRole("tablist")).toHaveCount(0);
  });

  test("tutte le risposte dell'API ricevute dal viewer sono prive di costi e righe", async ({ page }) => {
    const pending: Promise<string>[] = [];
    page.on("response", (r) => {
      if (r.url().includes("/api/v1/ce") && r.ok() && r.headers()["content-type"]?.includes("json")) {
        // un corpo non più disponibile (richiesta interrotta) non deve bloccare il test
        pending.push(Promise.race([r.text().catch(() => ""), new Promise<string>((done) => setTimeout(() => done(""), 4000))]));
      }
    });
    await page.goto("/ce");
    await expect(page.getByRole("link", { name: "PS-ALFA-ECOM-PJT" }).first()).toBeVisible();
    await open(page, "PS-ALFA-ECOM-PJT");
    await expect(page.getByText("Totale generale")).toBeVisible();
    const bodies = (await Promise.all(pending)).filter(Boolean);
    expect(bodies.length).toBeGreaterThanOrEqual(2);
    for (const body of bodies) {
      for (const secret of ['"cost"', '"margin"', "daily_cost", "daily_price", '"hours"', '"activity"', "Sviluppo catalogo", "calculation"]) {
        expect(body, `risposta API con "${secret}"`).not.toContain(secret);
      }
    }
  });

  test("esporta il riepilogo in PDF", async ({ page }) => {
    await open(page, "PS-ALFA-ECOM-PJT");
    await page.getByRole("button", { name: /^Esporta/ }).click();
    const download = page.waitForEvent("download");
    await page.getByRole("menuitem", { name: "PDF" }).click();
    const file = await download;
    expect(file.suggestedFilename()).toBe("PS-ALFA-ECOM-PJT_v1_riepilogo.pdf");
  });

  test("un CE non approvato non esiste per il viewer", async ({ page }) => {
    const found = await apiGet(page, PRESALE, "/api/v1/ce?code=GAMMA-DATA");
    const id = found.json.items[0].ce_id;
    await page.goto(`/ce/${id}`);
    await expect(page.getByRole("alert")).toContainText("non trovato");
  });
});
