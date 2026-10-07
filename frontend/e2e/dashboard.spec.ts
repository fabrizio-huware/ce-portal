import { expect, test, type Page } from "@playwright/test";

import { ADMIN, PRESALE, VIEWER, api, cleanup, createCe, expectNoPageOverflow, loginAs, openFilters } from "./helpers";

test.afterEach(async ({ page }) => cleanup(page));

const euro = (n: number) => n.toLocaleString("it-IT", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + " €";
const stat = (page: Page, label: string) => page.locator("div.card", { has: page.getByText(label, { exact: true }) }).first();

test.describe("portfolio", () => {
  test.beforeEach(async ({ page }) => loginAs(page, PRESALE));

  test("i numeri a video sono quelli dell'API", async ({ page, isMobile }) => {
    const server = (await api(page, PRESALE, "GET", "/api/v1/dashboard/portfolio")).json;
    if (isMobile) await page.getByRole("button", { name: "Menu" }).click();
    await page.getByRole("navigation", { name: isMobile ? "Principale mobile" : "Principale" }).getByRole("link", { name: "Dashboard" }).click();
    await expect(page).toHaveURL(/\/dashboard\/portfolio$/);
    await expect(stat(page, "Ricavi approvati")).toContainText(euro(Number(server.approved.revenue)));
    await expect(stat(page, "Ricavi approvati")).toContainText(`${server.approved.count} CE approvati`);
    await expect(stat(page, "Pipeline")).toContainText(euro(Number(server.pipeline.revenue)));
    await expect(stat(page, "Margine approvato")).toContainText(euro(Number(server.approved.margin)));
    await expect(page.getByText(/1 CE già approvato con una nuova versione in lavorazione/)).toBeVisible();
  });

  test("grafici, legenda e tabelle equivalenti per i lettori di schermo", async ({ page }) => {
    await page.goto("/dashboard/portfolio");
    await expect(page.getByText("Ricavi per mese").first()).toBeVisible();
    await expect(page.getByRole("list", { name: "Legenda" }).first()).toContainText("Approvati");
    await expect(page.getByRole("list", { name: "Legenda" }).first()).toContainText("Pipeline");
    const byClient = page.getByRole("table", { name: "Ricavi per cliente" });
    await expect(byClient.getByRole("rowheader")).toHaveCount(4); // 4 clienti nei dati di esempio
    await expect(page.getByRole("table", { name: "Ricavi per mese" }).getByRole("rowheader").first()).toHaveText("gen 2026");
    await expect(page.getByText("La vista per mese esclude la contingency")).toBeVisible();
  });

  test("senza pipeline restano solo gli approvati", async ({ page }) => {
    await page.goto("/dashboard/portfolio");
    await openFilters(page);
    await page.getByLabel("Includi la pipeline").uncheck();
    await expect(page).toHaveURL(/pipeline=0/);
    await expect(stat(page, "Pipeline")).toHaveCount(0);
    await expect(page.getByRole("link", { name: "PS-GAMMA-DATA-PJT" })).toHaveCount(0); // in approvazione: è pipeline
    await expect(page.getByRole("link", { name: "PS-BETA-CRM-PJT" })).toBeVisible();
    const server = (await api(page, PRESALE, "GET", "/api/v1/dashboard/portfolio?include_pipeline=false")).json;
    await expect(stat(page, "Ricavi approvati")).toContainText(euro(Number(server.approved.revenue)));
  });

  test("filtri per cliente, business unit e periodo", async ({ page }) => {
    await page.goto("/dashboard/portfolio");
    await openFilters(page);
    await page.getByLabel("Cliente", { exact: true }).selectOption({ label: "Beta Banca" });
    await expect(page.getByRole("link", { name: "PS-BETA-CRM-PJT" })).toBeVisible();
    await expect(page.getByRole("link", { name: "PS-ALFA-ECOM-PJT" })).toHaveCount(0);
    await page.getByRole("button", { name: "Azzera filtri" }).click();
    await page.getByLabel("Business unit", { exact: true }).fill("ai");
    await expect(page.getByRole("link", { name: "PS-ALFA-AI-PJT" })).toBeVisible();
    await expect(page.getByRole("link", { name: "PS-BETA-CRM-PJT" })).toHaveCount(0);
    await page.getByRole("button", { name: "Azzera filtri" }).click();
    await page.getByLabel("Attivi dal").fill("2026-12-01");
    await expect(page.getByRole("link", { name: "PS-GAMMA-DATA-PJT" })).toBeVisible(); // fino al 18/12
    await expect(page.getByRole("link", { name: "PS-ALFA-ECOM-PJT" })).toHaveCount(0); // finito a giugno
  });

  test("nessun risultato: messaggio chiaro", async ({ page }) => {
    await page.goto("/dashboard/portfolio?from=2030-01-01");
    await expect(page.getByRole("heading", { name: "Nessun conto economico nel periodo" })).toBeVisible();
  });

  test("esporta in Excel e in CSV", async ({ page }) => {
    await page.goto("/dashboard/portfolio");
    await expect(page.getByText("Ricavi per mese").first()).toBeVisible();
    for (const [label, ext] of [["Excel (tutte le tabelle)", "xlsx"], ["CSV (elenco dei CE)", "csv"]]) {
      await page.getByRole("button", { name: /^Esporta/ }).click();
      const download = page.waitForEvent("download");
      await page.getByRole("menuitem", { name: label }).click();
      expect((await download).suggestedFilename()).toMatch(new RegExp(`^portfolio_ce_\\d{8}\\.${ext}$`));
    }
  });

  test("dal portfolio si apre il dettaglio del CE", async ({ page }) => {
    await page.goto("/dashboard/portfolio");
    await page.getByRole("link", { name: "PS-BETA-CRM-PJT" }).click();
    await expect(page.getByRole("heading", { name: "PS-BETA-CRM-PJT", level: 1 })).toBeVisible();
  });
});

test.describe("carico risorse", () => {
  const Y = "from=2026-01&to=2026-12";

  test("mostra chi supera il 100% e dove, con simbolo e numero (non solo colore)", async ({ page }) => {
    await loginAs(page, PRESALE);
    await page.goto(`/dashboard/risorse?${Y}&pipeline=1`);
    const server = (await api(page, PRESALE, "GET", "/api/v1/dashboard/resources?date_from=2026-01-01&date_to=2026-12-01&include_pipeline=true")).json;
    const over = (server.employees as { name: string; overloaded_months: number }[]).filter((e) => e.overloaded_months > 0);
    expect(over.length).toBeGreaterThan(0); // i dati di esempio contengono sovraccarichi
    await expect(stat(page, "Persone in sovraccarico")).toContainText(String(over.length));
    const table = page.getByRole("table", { name: /Impegno dei collaboratori/ }).or(page.locator("table").first());
    for (const person of over) {
      const row = page.getByRole("row").filter({ has: page.getByRole("rowheader", { name: new RegExp(person.name) }) });
      await expect(row).toContainText("⚠");
      await expect(row.locator("td").last()).toHaveText(String(person.overloaded_months));
    }
    expect(await table.count()).toBeGreaterThan(0);
  });

  test("senza pipeline il sovraccarico dipende solo dagli approvati", async ({ page }) => {
    await loginAs(page, PRESALE);
    await page.goto(`/dashboard/risorse?${Y}`);
    await expect(page.getByText("solo approvati")).toBeVisible();
    const server = (await api(page, PRESALE, "GET", "/api/v1/dashboard/resources?date_from=2026-01-01&date_to=2026-12-01")).json;
    const over = (server.employees as { overloaded_months: number }[]).filter((e) => e.overloaded_months > 0).length;
    await expect(stat(page, "Persone in sovraccarico")).toContainText(String(over));
  });

  test("un CE appena creato con troppe ore compare in sovraccarico, e sparisce quando lo si elimina", async ({ page }) => {
    const ce = await createCe(page, { start: "2026-12-01", end: "2026-12-18", phases: [{ name: "Delivery", lines: [{ activity: "Troppo lavoro", profile: "Senior", hours: "300", employee: "Conti Sara" }] }] });
    await api(page, PRESALE, "POST", `/api/v1/ce/${ce.id}/submit`);
    await api(page, ADMIN, "POST", `/api/v1/ce/${ce.id}/approve`);
    await loginAs(page, PRESALE);
    await page.goto("/dashboard/risorse?from=2026-12&to=2026-12"); // a dicembre nessun CE approvato ha impegni: resta solo questo
    const row = page.getByRole("row").filter({ has: page.getByRole("rowheader", { name: /Sara Conti/ }) });
    await expect(row).toContainText("⚠");
    await expect(row).toContainText("%");
    await expect(stat(page, "Persone in sovraccarico")).toContainText("1");
    await api(page, ADMIN, "DELETE", `/api/v1/ce/${ce.id}`);
    await page.reload();
    await expect(page.getByRole("heading", { name: "Nessun impegno nel periodo" })).toBeVisible();
  });

  test("filtri per profilo e collaboratore", async ({ page }) => {
    await loginAs(page, PRESALE);
    await page.goto(`/dashboard/risorse?${Y}`);
    await openFilters(page);
    await page.getByLabel("Collaboratore", { exact: true }).selectOption({ label: "Ferri Luca" });
    await expect(page.getByRole("rowheader", { name: /Luca Ferri/ })).toBeVisible();
    await expect(page.getByRole("rowheader", { name: /Giulia Rossi/ })).toHaveCount(0);
    await page.getByRole("button", { name: "Azzera filtri" }).click();
    await page.getByLabel("Profilo", { exact: true }).selectOption({ label: "Manager" });
    await expect(page.getByRole("rowheader", { name: /Giulia Rossi/ })).toBeVisible();
    await expect(page.getByRole("rowheader", { name: /Luca Ferri/ })).toHaveCount(0);
  });

  test("periodo troppo lungo: il motivo è spiegato", async ({ page }) => {
    await loginAs(page, PRESALE);
    await page.goto("/dashboard/risorse?from=2026-01&to=2030-12");
    await expect(page.getByRole("alert")).toContainText("massimo");
  });

  test("esporta in Excel e in CSV", async ({ page }) => {
    await loginAs(page, PRESALE);
    await page.goto(`/dashboard/risorse?${Y}`);
    await expect(page.getByRole("heading", { name: "Impegno dei collaboratori" })).toBeVisible();
    for (const [label, ext] of [["Excel (collaboratori, profili, dati)", "xlsx"], ["CSV (dati per mese)", "csv"]]) {
      await page.getByRole("button", { name: /^Esporta/ }).click();
      const download = page.waitForEvent("download");
      await page.getByRole("menuitem", { name: label }).click();
      expect((await download).suggestedFilename()).toMatch(new RegExp(`^carico_risorse_\\d{8}\\.${ext}$`));
    }
  });
});

test.describe("permessi e schermo piccolo", () => {
  test("il viewer non vede la voce Dashboard e le pagine sono negate", async ({ page }) => {
    await loginAs(page, VIEWER);
    await expect(page.getByRole("link", { name: "Dashboard" })).toHaveCount(0);
    for (const path of ["/dashboard/portfolio", "/dashboard/risorse"]) {
      await page.goto(path);
      await expect(page.getByRole("alert")).toContainText("riservate");
    }
    await page.goto("/dashboard/portfolio");
    // nemmeno l'API risponde al viewer
    expect((await api(page, VIEWER, "GET", "/api/v1/dashboard/portfolio")).status).toBe(403);
  });

  test("le dashboard stanno nella larghezza dello schermo", async ({ page }) => {
    await loginAs(page, PRESALE);
    for (const path of ["/dashboard/portfolio", "/dashboard/risorse?from=2026-01&to=2026-12&pipeline=1"]) {
      await page.goto(path);
      await expect(page.getByText(/Ricavi per mese|Impegno dei collaboratori/).first()).toBeVisible();
      await expectNoPageOverflow(page);
    }
  });
});
