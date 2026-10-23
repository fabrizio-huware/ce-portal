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
    // il Portfolio filtra per business unit (i CE che la coinvolgono): ALFA-AI coinvolge Cloud, BETA-MIG solo Data & AI
    await page.getByLabel("Business unit", { exact: true }).selectOption({ label: "Cloud & Infrastructure" });
    await expect(page.getByRole("link", { name: "PS-ALFA-AI-PJT" })).toBeVisible();
    await expect(page.getByRole("link", { name: "PS-BETA-MIG-PJT" })).toHaveCount(0);
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

  test("le celle mostrano percentuale, giorni e ore; l'interruttore cambia cosa si vede e resta nell'indirizzo", async ({ page }) => {
    // 300 ore = 37,5 giornate in un solo mese: oltre il 100% della capacità, quindi anche il sovraccarico
    const ce = await createCe(page, { start: "2026-12-01", end: "2026-12-18", phases: [{ name: "Delivery", lines: [{ activity: "Troppo lavoro", profile: "Senior", hours: "300", employee: "Conti Sara" }] }] });
    await api(page, PRESALE, "POST", `/api/v1/ce/${ce.id}/submit`);
    await api(page, ADMIN, "POST", `/api/v1/ce/${ce.id}/approve`);
    const server = (await api(page, PRESALE, "GET", "/api/v1/dashboard/resources?date_from=2026-12-01&date_to=2026-12-01")).json;
    const cell = (server.employees as { name: string; cells: { fte: string; days: string; hours: string }[] }[]).find((e) => e.name.includes("Sara Conti"))!.cells[0];
    const pctText = `${Math.round(Number(cell.fte) * 100)}%`;
    expect(Number(cell.days)).toBeCloseTo(37.5, 2);
    expect(Number(cell.hours)).toBeCloseTo(300, 2); // le ore le calcola il server: 37,5 giorni × 8

    await loginAs(page, PRESALE);
    await page.goto("/dashboard/risorse?from=2026-12&to=2026-12");
    const row = page.getByRole("row").filter({ has: page.getByRole("rowheader", { name: /Sara Conti/ }) });
    const pressed = (name: string) => page.getByRole("button", { name, exact: true });

    // predefinito: entrambi
    await expect(pressed("Entrambi")).toHaveAttribute("aria-pressed", "true");
    await expect(row).toContainText(`⚠ ${pctText}`);
    await expect(row).toContainText("37,5 gg");
    await expect(page).not.toHaveURL(/celle=/);
    // chi usa uno screen reader sente sempre tutto, qualunque cosa si veda
    await expect(row.getByLabel(new RegExp(`dic 2026: ${pctText}, sovraccarico, 37,50 giorni`, "i"))).toBeVisible();

    await pressed("Giorni").click();
    await expect(page).toHaveURL(/celle=giorni/);
    await expect(row).toContainText("⚠ 37,5");
    await expect(row).not.toContainText("%");
    await expect(row).not.toContainText("gg");
    await expect(row.getByLabel(new RegExp(`dic 2026: ${pctText}`, "i"))).toBeVisible();

    await pressed("Ore").click();
    await expect(page).toHaveURL(/celle=ore/);
    await expect(row).toContainText("⚠ 300,0"); // 300 ore, come dice il server
    await expect(row).not.toContainText("%");
    await expect(row).not.toContainText("gg");
    await expect(row.getByLabel(new RegExp(`dic 2026: ${pctText}, sovraccarico, 37,50 giorni.*300,00 ore`, "i"))).toBeVisible();
    // il totale a destra e la riga della capacità del mese restano in giorni
    await expect(row).toContainText("37,50");
    await expect(page.getByText("Giorni lavorativi del mese", { exact: true })).toBeVisible();
    await expect(page.getByLabel("Impegno dei collaboratori per mese").getByRole("columnheader", { name: "Giorni", exact: true })).toBeVisible();

    await pressed("Percentuale").click();
    await expect(page).toHaveURL(/celle=pct/);
    await expect(row).toContainText(`⚠ ${pctText}`);
    await expect(row).not.toContainText("gg");

    await pressed("Entrambi").click();
    await expect(page).not.toHaveURL(/celle=/);
    await expect(row).toContainText("37,5 gg");
  });

  test("la scelta si ricorda ricaricando la pagina e non sparisce con «Azzera filtri»", async ({ page }) => {
    await loginAs(page, PRESALE);
    await page.goto(`/dashboard/risorse?${Y}&celle=giorni`);
    await expect(page.getByRole("button", { name: "Giorni", exact: true })).toHaveAttribute("aria-pressed", "true");
    await openFilters(page);
    await page.getByLabel("Profilo", { exact: true }).selectOption({ label: "Manager" });
    await expect(page.getByRole("rowheader", { name: /Giulia Rossi/ })).toBeVisible();
    await page.getByRole("button", { name: "Azzera filtri" }).click();
    await expect(page).toHaveURL(/celle=giorni/);
    await expect(page).not.toHaveURL(/profile/);
    await expect(page.getByRole("button", { name: "Giorni", exact: true })).toHaveAttribute("aria-pressed", "true");
    // un valore sconosciuto nell'indirizzo non rompe nulla: si torna a «Entrambi»
    await page.goto(`/dashboard/risorse?${Y}&celle=qualcosa`);
    await expect(page.getByRole("button", { name: "Entrambi", exact: true })).toHaveAttribute("aria-pressed", "true");
  });

  test("la modalità Ore si ricorda ricaricando la pagina e non sparisce con «Azzera filtri»", async ({ page }) => {
    await loginAs(page, PRESALE);
    await page.goto(`/dashboard/risorse?${Y}&celle=ore`);
    await expect(page.getByRole("button", { name: "Ore", exact: true })).toHaveAttribute("aria-pressed", "true");
    await openFilters(page);
    await page.getByLabel("Profilo", { exact: true }).selectOption({ label: "Manager" });
    await expect(page.getByRole("rowheader", { name: /Giulia Rossi/ })).toBeVisible();
    await page.getByRole("button", { name: "Azzera filtri" }).click();
    await expect(page).toHaveURL(/celle=ore/);
    await expect(page.getByRole("button", { name: "Ore", exact: true })).toHaveAttribute("aria-pressed", "true");
    // le quattro scelte ci sono, nell'ordine voluto
    await expect(page.getByRole("group", { name: "Cosa mostrare nelle celle" }).getByRole("button")).toHaveText(["Percentuale", "Giorni", "Ore", "Entrambi"]);
  });

  test("la sezione per practice mostra persone, percentuale e giorni, segue il selettore e il filtro", async ({ page }) => {
    const id = Date.now().toString(36);
    const senior = (await api(page, ADMIN, "GET", "/api/v1/profiles")).json.find((p: { name: string }) => p.name === "Senior");
    const mkPractice = async (name: string) => (await api(page, ADMIN, "POST", "/api/v1/practices", { name })).json;
    const mkEmployee = async (last: string, practice: { id: string }) =>
      (await api(page, ADMIN, "POST", "/api/v1/employees", { first_name: "Prova", last_name: last, default_profile_id: senior.id, practice_id: practice.id })).json;
    const pa = await mkPractice(`PracA ${id}`);
    const pb = await mkPractice(`PracB ${id}`);
    const people = [await mkEmployee(`Pa1${id}`, pa), await mkEmployee(`Pa2${id}`, pa), await mkEmployee(`Pb1${id}`, pb)];
    try {
      // settembre 2026: 22 giorni lavorativi. PracA: 11 + 22 giorni su 2 persone = 75%. PracB: 33 giorni su 1 persona = 150%
      for (const [emp, hours] of [[people[0], "88"], [people[1], "176"], [people[2], "264"]] as const) {
        const ce = await createCe(page, { start: "2026-09-01", end: "2026-09-30", phases: [{ name: "Delivery", lines: [{ activity: "Impegno", profile: "Senior", hours, employee: `${emp.last_name} Prova` }] }] });
        await api(page, PRESALE, "POST", `/api/v1/ce/${ce.id}/submit`);
        await api(page, ADMIN, "POST", `/api/v1/ce/${ce.id}/approve`);
      }
      const server = (await api(page, PRESALE, "GET", "/api/v1/dashboard/resources?date_from=2026-09-01&date_to=2026-09-01")).json;
      const served = (name: string) => (server.practices as { name: string; persons: number; cells: { fte: string; days: string }[] }[]).find((r) => r.name === name)!;
      expect(served(pa.name).persons).toBe(2);
      const pctA = `${Math.round(Number(served(pa.name).cells[0].fte) * 100)}%`;
      expect(pctA).toBe("75%");

      await loginAs(page, PRESALE);
      await page.goto("/dashboard/risorse?from=2026-09&to=2026-09");
      await expect(page.getByRole("heading", { name: "Impegno per practice" })).toBeVisible();
      const rowOf = (name: string) => page.getByRole("row").filter({ has: page.getByRole("rowheader", { name: new RegExp(`^${name}`) }) });
      const rowA = rowOf(pa.name);
      const rowB = rowOf(pb.name);
      await expect(rowA).toContainText("2 persone");
      await expect(rowA).toContainText(pctA);
      await expect(rowA).toContainText("33,0 gg");
      await expect(rowA).not.toContainText("⚠");
      await expect(rowB).toContainText("1 persona");
      await expect(rowB).toContainText("⚠ 150%");
      await expect(rowA.getByLabel(/media di 2 persone/)).toBeVisible(); // lo screen reader sente che è una media

      const pressed = (name: string) => page.getByRole("button", { name, exact: true });
      await pressed("Giorni").click(); // il selettore vale anche per le practice
      await expect(rowA).toContainText("33,0");
      await expect(rowA).not.toContainText("%");
      await pressed("Ore").click();
      await expect(rowA).toContainText("264,0");
      await pressed("Percentuale").click();
      await expect(rowA).toContainText(pctA);
      await expect(rowA).not.toContainText("gg");
      await pressed("Entrambi").click();

      await expect(page.getByRole("rowheader", { name: new RegExp(`Prova Pa1${id}`) })).toBeVisible(); // le persone sono sotto
      await openFilters(page);
      await page.getByLabel("Practice", { exact: true }).selectOption({ label: pa.name });
      await expect(page).toHaveURL(new RegExp(`practice=${pa.id}`));
      await expect(page.getByLabel("Impegno delle practice per mese").getByRole("rowheader")).toHaveCount(1);
      await expect(page.getByRole("rowheader", { name: new RegExp(`Prova Pb1${id}`) })).toHaveCount(0); // l'altra practice è fuori
      await expect(page.getByRole("rowheader", { name: new RegExp(`Prova Pa2${id}`) })).toBeVisible();

      const request = page.waitForRequest((r) => r.url().includes("/resources/export") && r.url().includes(`practice_id=${pa.id}`));
      await page.getByRole("button", { name: /Esporta/ }).click();
      await page.getByRole("menuitem", { name: /CSV/ }).click();
      await request; // l'esportazione porta con sé il filtro per practice
    } finally {
      for (const e of people) await api(page, ADMIN, "PATCH", `/api/v1/employees/${e.id}`, { is_active: false });
      for (const p of [pa, pb]) await api(page, ADMIN, "PATCH", `/api/v1/practices/${p.id}`, { is_active: false });
    }
  });

  test("senza impegno la cella resta un trattino, in ogni modalità", async ({ page }) => {
    await loginAs(page, PRESALE);
    for (const celle of ["", "&celle=pct", "&celle=giorni", "&celle=ore"]) {
      await page.goto(`/dashboard/risorse?${Y}&pipeline=1${celle}`); // con la pipeline compaiono anche le persone che hanno solo impegni non ancora approvati
      const row = page.getByRole("row").filter({ has: page.getByRole("rowheader", { name: /Chiara Villa/ }) });
      await expect(row.locator("td").first()).toHaveText("—"); // gennaio-marzo: nessun impegno per questa persona
    }
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
    for (const [label, ext] of [["Excel (collaboratori, practice, profili, dati)", "xlsx"], ["CSV (dati per mese)", "csv"]]) {
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

test.describe("carico risorse per business unit", () => {
  test("c'è la sezione per business unit e il filtro la restringe", async ({ page }) => {
    await loginAs(page, PRESALE);
    await page.goto("/dashboard/risorse?from=2026-01&to=2026-12&pipeline=1");
    const section = page.getByRole("region", { name: "Impegno per business unit" });
    await expect(section).toBeVisible();
    await expect(section).toContainText("Data & AI");
    await expect(section).toContainText("Cloud & Infrastructure");
    await openFilters(page);
    await page.getByLabel("Business unit", { exact: true }).selectOption({ label: "Cloud & Infrastructure" });
    await expect(section).toContainText("Cloud & Infrastructure");
    await expect(section).not.toContainText("Data & AI");
  });
});

