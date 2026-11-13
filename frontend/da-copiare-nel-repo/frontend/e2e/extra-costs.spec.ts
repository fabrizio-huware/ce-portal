import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

import { PRESALE, VIEWER, api, cleanup, createCe, expectNoPageOverflow, loginAs } from "./helpers";

test.afterEach(async ({ page }) => cleanup(page));

const PREVIEW = (page: Page) => page.getByRole("region", { name: "Anteprima dei totali" });
const ONE_LINE = [{ name: "Delivery", lines: [{ activity: "Sviluppo", profile: "Senior", hours: "16" }] }]; // 2 giorni: 1.700 € di ricavi
const LOADED = (page: Page) => expect(page.locator(".opacity-60")).toHaveCount(0); // anteprima aggiornata

async function openEditor(page: Page, id: string) {
  await loginAs(page, PRESALE);
  await page.goto(`/ce/${id}/modifica`);
  await expect(page.getByRole("heading", { name: "Fasi e righe" })).toBeVisible();
}

async function addCost(page: Page, n: number, description: string, cost: string, markup?: string) {
  await page.getByRole("button", { name: "+ Aggiungi un costo vario" }).click();
  await page.getByLabel(`Descrizione del costo vario ${n}`, { exact: true }).fill(description);
  await page.getByLabel(`Costo del costo vario ${n}`, { exact: true }).fill(cost);
  if (markup !== undefined) await page.getByLabel(`Ricarico del costo vario ${n}`, { exact: true }).fill(markup);
}

test.describe("costi vari", () => {
  test("si aggiungono righe, il totale di riga e quello del CE sono calcolati dal server e restano dopo il salvataggio", async ({ page }) => {
    const ce = await createCe(page, { phases: ONE_LINE });
    await openEditor(page, ce.id);
    await expect(PREVIEW(page)).toContainText("1.700,00 €");
    await expect(page.getByText("Nessun costo vario.")).toBeVisible();

    await addCost(page, 1, "Viaggi e trasferte", "1000", "20");
    await addCost(page, 2, "Licenze", "333,33", "15,5");
    const panel = page.getByRole("region", { name: "Costi vari" });
    // prima il totale finale: finché l'anteprima non è arrivata una riga può comparire due volte
    await expect(PREVIEW(page)).toContainText("3.285,00 €"); // 1.700 + 1.585
    await expect(panel.getByText("1.585,00 €")).toBeVisible(); // totale costi vari
    await expect(panel.getByText("1.200,00 €")).toBeVisible(); // 1.000 + 20%
    await expect(panel.getByText("385,00 €")).toBeVisible(); // 333,33 + 15,5% = 384,99615 -> 385,00
    await expect(PREVIEW(page)).toContainText("1.993,33 €"); // costi: 660 + 1.333,33
    await LOADED(page);

    await page.getByRole("button", { name: "Salva" }).click();
    await expect(page.getByText("Modifiche salvate")).toBeVisible();
    await page.reload();
    await expect(page.getByLabel("Descrizione del costo vario 1", { exact: true })).toHaveValue("Viaggi e trasferte");
    await expect(page.getByLabel("Costo del costo vario 2", { exact: true })).toHaveValue("333,33");
    await expect(page.getByLabel("Ricarico del costo vario 2", { exact: true })).toHaveValue("15,5");
    await expect(page.getByLabel("Ricarico del costo vario 1", { exact: true })).toHaveValue("20");
    await expect(PREVIEW(page)).toContainText("3.285,00 €");

    const saved = await api(page, PRESALE, "GET", `/api/v1/ce/${ce.id}`);
    expect(saved.json.extra_costs.map((e: { description: string; cost: string; markup_pct: string }) => [e.description, e.cost, e.markup_pct])).toEqual([
      ["Viaggi e trasferte", "1000.00", "20.00"],
      ["Licenze", "333.33", "15.50"],
    ]);
    expect(saved.json.calculation.total.revenue).toBe("3285.00");
  });

  test("il dettaglio mostra le righe, la riga «Costi vari» nel riepilogo e la nota sullo staffing", async ({ page }) => {
    const ce = await createCe(page, { phases: ONE_LINE });
    await openEditor(page, ce.id);
    await addCost(page, 1, "Viaggi e trasferte", "1000", "20");
    await page.getByRole("button", { name: "Salva" }).click();
    await expect(page.getByText("Modifiche salvate")).toBeVisible();

    await page.goto(`/ce/${ce.id}`);
    const group = page.getByRole("group", { name: "Costi vari" });
    await expect(group.getByText("Viaggi e trasferte")).toBeVisible();
    await expect(group.getByText("20,00%")).toBeVisible();
    await expect(group.getByText("1.200,00 €").first()).toBeVisible();
    await page.getByRole("tab", { name: "Riepilogo" }).click();
    const summary = page.getByRole("region", { name: "Ricavi e costi" });
    await expect(summary.getByRole("row", { name: /Costi vari/ })).toContainText("1.200,00 €");
    await expect(summary.getByRole("row", { name: /^Totale/ })).toContainText("2.900,00 €");
    await page.getByRole("tab", { name: "Staffing mensile" }).click();
    await expect(page.getByText("I costi vari non hanno un mese")).toBeVisible();
  });

  test("senza costi vari il dettaglio non mostra né la sezione né la riga", async ({ page }) => {
    const ce = await createCe(page, { phases: ONE_LINE });
    await loginAs(page, PRESALE);
    await page.goto(`/ce/${ce.id}`);
    await expect(page.getByRole("heading", { name: ce.code, level: 1 })).toBeVisible();
    await expect(page.getByRole("group", { name: "Costi vari" })).toHaveCount(0);
    await page.getByRole("tab", { name: "Riepilogo" }).click();
    await expect(page.getByRole("row", { name: /Costi vari/ })).toHaveCount(0);
  });

  test("controlli immediati: manca la descrizione; una riga vuota non blocca", async ({ page }) => {
    const ce = await createCe(page, { phases: ONE_LINE });
    await openEditor(page, ce.id);
    await page.getByRole("button", { name: "+ Aggiungi un costo vario" }).click(); // riga vuota: si ignora
    await expect(page.getByRole("button", { name: "Salva" })).toBeDisabled(); // nessuna modifica vera
    await page.getByLabel("Costo del costo vario 1", { exact: true }).fill("50");
    await page.getByRole("button", { name: "Salva" }).click();
    await expect(page.getByRole("alert")).toContainText("Costi vari, riga 1: manca la descrizione");
    await page.getByLabel("Descrizione del costo vario 1", { exact: true }).fill("Hotel");
    await page.getByLabel("Ricarico del costo vario 1", { exact: true }).fill("1001");
    await page.getByRole("button", { name: "Salva" }).click();
    await expect(page.getByRole("alert")).toContainText("ricarico, al massimo 1000");
    await page.getByLabel("Ricarico del costo vario 1", { exact: true }).fill("10");
    await page.getByRole("button", { name: "Salva" }).click();
    await expect(page.getByText("Modifiche salvate")).toBeVisible();
    expect((await api(page, PRESALE, "GET", `/api/v1/ce/${ce.id}`)).json.calculation.extras.revenue).toBe("55.00");
  });

  test("un ricarico negativo riduce il totale di riga; sotto -100% è segnalato", async ({ page }) => {
    const ce = await createCe(page, { phases: ONE_LINE });
    await openEditor(page, ce.id);
    await addCost(page, 1, "Sconto fornitore", "1000", "-25");
    await expect(PREVIEW(page)).toContainText("2.450,00 €"); // 1.700 + 750
    await expect(page.getByRole("region", { name: "Costi vari" }).getByText("750,00 €").first()).toBeVisible();
    await page.getByLabel("Ricarico del costo vario 1", { exact: true }).fill("-100,5");
    await expect(page.getByLabel("Ricarico del costo vario 1", { exact: true })).toHaveAttribute("aria-invalid", "true");
    await page.getByRole("button", { name: "Salva" }).click();
    await expect(page.getByRole("alert")).toContainText("ricarico, almeno -100");
    await page.getByLabel("Ricarico del costo vario 1", { exact: true }).fill("-25");
    await expect(page.getByLabel("Ricarico del costo vario 1", { exact: true })).not.toHaveAttribute("aria-invalid", "true");
    await LOADED(page);
    await page.getByRole("button", { name: "Salva" }).click();
    await expect(page.getByText("Modifiche salvate")).toBeVisible();
    await page.reload();
    await expect(page.getByLabel("Ricarico del costo vario 1", { exact: true })).toHaveValue("-25");
    const calc = (await api(page, PRESALE, "GET", `/api/v1/ce/${ce.id}`)).json.calculation;
    expect(calc.extras.revenue).toBe("750.00");
    expect(calc.extras.margin).toBe("-250.00");
  });

  test("si sposta e si elimina una riga: il totale torna com'era", async ({ page }) => {
    const ce = await createCe(page, { phases: ONE_LINE });
    await openEditor(page, ce.id);
    await addCost(page, 1, "Prima", "100", "0");
    await addCost(page, 2, "Seconda", "200", "0");
    await page.getByRole("button", { name: "Azioni del costo vario 2" }).click();
    await page.getByRole("menuitem", { name: "Sposta su" }).click();
    await expect(page.getByLabel("Descrizione del costo vario 1", { exact: true })).toHaveValue("Seconda");
    await page.getByRole("button", { name: "Azioni del costo vario 1" }).click();
    await page.getByRole("menuitem", { name: "Elimina la riga" }).click();
    await expect(page.getByLabel("Descrizione del costo vario 1", { exact: true })).toHaveValue("Prima");
    await expect(page.getByLabel("Descrizione del costo vario 2", { exact: true })).toHaveCount(0);
    await expect(PREVIEW(page)).toContainText("1.800,00 €"); // 1.700 + 100
  });

  test("il viewer vede il prezzo totale e una sola voce \"Costi vari\", mai righe, costi o ricarico", async ({ page }) => {
    const ce = await createCe(page, { phases: ONE_LINE });
    const content = (await api(page, PRESALE, "GET", `/api/v1/ce/${ce.id}`)).json;
    const put = await api(page, PRESALE, "PUT", `/api/v1/ce/${ce.id}/content`, {
      expected_revision: content.version.revision,
      header: { client_id: ce.clientId, project_name: `Progetto ${ce.code}`, start_date: ce.start, end_date: ce.end, planning_mode: "hours" },
      phases: content.phases.map((p: { name: string; contingency_pct: string; lines: { activity: string; profile_id: string; hours: string }[] }) => ({
        name: p.name, contingency_pct: p.contingency_pct, lines: p.lines.map((l) => ({ activity: l.activity, profile_id: l.profile_id, hours: l.hours })),
      })),
      extra_costs: [{ description: "Voce riservata XYZ", cost: "777.00", markup_pct: "10" }],
    });
    expect(put.status, JSON.stringify(put.json)).toBe(200);
    expect((await api(page, PRESALE, "POST", `/api/v1/ce/${ce.id}/submit`)).status).toBe(200);
    expect((await api(page, "admin@huware.com", "POST", `/api/v1/ce/${ce.id}/approve`)).status).toBe(200);
    await loginAs(page, VIEWER);
    await page.goto(`/ce/${ce.id}`);
    await expect(page.getByRole("heading", { name: ce.code, level: 1 })).toBeVisible();
    await expect(page.getByText("2.554,70 €").first()).toBeVisible(); // 1.700 + 777 x 1,10 = 854,70
    await expect(page.getByRole("cell", { name: "Costi vari", exact: true })).toHaveCount(1);
    await expect(page.getByText("854,70 €").first()).toBeVisible(); // solo il ricavo della voce
    for (const secret of ["Voce riservata XYZ", "777", "ricarico", "Ricarico"]) await expect(page.getByText(secret, { exact: false })).toHaveCount(0);
  });

  test("senza scorrimento della pagina e senza violazioni di accessibilità", async ({ page }) => {
    const ce = await createCe(page, { phases: ONE_LINE });
    await openEditor(page, ce.id);
    await addCost(page, 1, "Viaggi e trasferte", "1000", "20");
    await expect(PREVIEW(page)).toContainText("2.900,00 €");
    await LOADED(page);
    await expectNoPageOverflow(page);
    const axe = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).analyze();
    expect(axe.violations.map((v) => `${v.id}: ${v.nodes[0]?.target.join(" ")}`)).toEqual([]);
  });
});
