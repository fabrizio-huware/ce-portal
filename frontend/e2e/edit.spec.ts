import { expect, test, type Page } from "@playwright/test";

import { ADMIN, PRESALE, VIEWER, api, cleanup, createCe, expectNoPageOverflow, loginAs, putContent, track, uniqueCode } from "./helpers";

test.afterEach(async ({ page }) => cleanup(page));

const PREVIEW = (page: Page) => page.getByRole("region", { name: "Anteprima dei totali" });
const row = (page: Page, what: string, n = 1, phase = "Delivery") => page.getByLabel(`${what} ${n} della fase ${phase}`, { exact: true });
const ONE_LINE = [{ name: "Delivery", lines: [{ activity: "Sviluppo", profile: "Senior", hours: "16" }] }];

async function openEditor(page: Page, id: string, who = PRESALE) {
  await loginAs(page, who);
  await page.goto(`/ce/${id}/modifica`);
  await expect(page.getByRole("heading", { name: "Fasi e righe" })).toBeVisible();
}

test.describe("nuovo CE", () => {
  test("il modulo crea il CE con le fasi standard e apre l'editor", async ({ page }) => {
    await loginAs(page, PRESALE);
    await page.getByRole("link", { name: "+ Nuovo CE" }).click();
    const code = uniqueCode();
    await page.getByLabel("Codice del CE").fill(code);
    await page.getByLabel("Cliente").selectOption({ label: "Alfa Retail" });
    await page.getByLabel("Nome del progetto").fill("Prova automatica");
    await page.getByLabel("Inizio").fill("2026-03-02");
    await page.getByLabel("Fine").fill("2026-05-29");
    await page.getByRole("button", { name: "Crea e inizia a compilare" }).click();
    await expect(page).toHaveURL(/\/ce\/[0-9a-f-]+\/modifica$/);
    track(page.url().match(/\/ce\/([0-9a-f-]+)\//)![1]);
    await expect(page.getByRole("heading", { name: code, level: 1 })).toBeVisible();
    for (const phase of ["Project Management", "Analysis", "Go-Live"]) await expect(page.locator(`input[value="${phase}"]`)).toHaveCount(1);
    await expect(page.getByRole("region", { name: /^Fase \d$/ })).toHaveCount(9);
  });

  test("il modulo spiega cosa manca e controlla il periodo", async ({ page }) => {
    await loginAs(page, PRESALE);
    await page.goto("/ce/nuovo");
    await page.getByRole("button", { name: "Crea e inizia a compilare" }).click();
    const alert = page.getByRole("alert");
    for (const text of ["Indica il codice", "Scegli il cliente", "nome del progetto", "date di inizio e fine"]) await expect(alert).toContainText(text);
    await page.getByLabel("Inizio").fill("2026-05-01");
    await page.getByLabel("Fine").fill("2026-04-01");
    await expect(alert).toContainText("La data di fine precede quella di inizio");
    await page.getByLabel("Fine").fill("2027-12-31");
    await expect(alert).toContainText("12 mesi");
  });

  test("un codice già usato è rifiutato dal server con un messaggio chiaro", async ({ page }) => {
    await loginAs(page, PRESALE);
    await page.goto("/ce/nuovo");
    await page.getByLabel("Codice del CE").fill("PS-BETA-CRM-PJT");
    await page.getByLabel("Cliente").selectOption({ label: "Alfa Retail" });
    await page.getByLabel("Nome del progetto").fill("Doppione");
    await page.getByLabel("Inizio").fill("2026-03-02");
    await page.getByLabel("Fine").fill("2026-05-29");
    await page.getByRole("button", { name: "Crea e inizia a compilare" }).click();
    await expect(page.getByRole("alert")).toContainText(/esiste già|già in uso|già presente/i);
    await expect(page).toHaveURL(/\/ce\/nuovo$/);
  });

  test("si può creare un cliente senza lasciare il modulo", async ({ page }) => {
    await loginAs(page, PRESALE);
    await page.goto("/ce/nuovo");
    const name = `Cliente prova ${Date.now().toString(36)}`;
    await page.getByRole("button", { name: "+ Nuovo" }).click();
    await page.getByLabel("Nome del cliente").fill(name);
    await page.getByRole("button", { name: "Crea cliente" }).click();
    await expect(page.getByLabel("Cliente", { exact: true })).toHaveValue(/.+/);
    await expect(page.getByLabel("Cliente", { exact: true }).locator("option:checked")).toHaveText(name);
  });
});

test.describe("editor a ore", () => {
  test("scrivere le ore aggiorna i totali (calcolo del server) e si salva", async ({ page }) => {
    const ce = await createCe(page, { phases: [{ name: "Delivery", lines: [] }] });
    await openEditor(page, ce.id);
    await page.getByRole("button", { name: "+ Aggiungi una riga a questa fase" }).click();
    await row(page, "Attività").fill("Sviluppo");
    await row(page, "Profilo").selectOption({ label: "Senior" });
    await row(page, "Ore").fill("16");
    await expect(PREVIEW(page)).toContainText("1.700,00 €"); // 2 giornate x 850
    await expect(PREVIEW(page)).toContainText("Calcolo aggiornato");
    await expect(page.getByText("Modifiche non salvate")).toBeVisible();
    await row(page, "Ore").fill("16,5"); // virgola decimale all'italiana
    await expect(PREVIEW(page)).toContainText("1.753,13 €"); // 2,0625 giornate x 850
    await page.getByRole("button", { name: "Salva" }).click();
    await expect(page.getByText(/Modifiche salvate/)).toBeVisible();
    await expect(page.getByText("Tutto salvato")).toBeVisible();
    // tutto è davvero salvato: lo conferma la pagina di dettaglio
    await page.goto(`/ce/${ce.id}`);
    await expect(page.getByText("1.753,13 €").first()).toBeVisible();
    await expect(page.getByText("Sviluppo")).toBeVisible();
  });

  test("contingency e sconto massimo", async ({ page }) => {
    const ce = await createCe(page, { phases: ONE_LINE });
    await openEditor(page, ce.id);
    await page.getByLabel("Contingency della fase Delivery").fill("10");
    await expect(PREVIEW(page)).toContainText("1.870,00 €"); // 1.700 + 10%
    await expect(page.getByText("Ricavo da contingency (senza costi)")).toBeVisible();
    await page.getByLabel("Max sconto %").fill("10");
    await page.getByRole("button", { name: "Salva" }).click();
    await expect(page.getByText(/Modifiche salvate/)).toBeVisible();
    await page.goto(`/ce/${ce.id}`);
    await expect(page.getByText("1.683,00 €")).toBeVisible(); // prezzo minimo = 1.870 x 0,90
  });

  test("scegliendo il collaboratore si propone il suo profilo", async ({ page }) => {
    const ce = await createCe(page, { phases: [{ name: "Delivery", lines: [{ activity: "Test", profile: "Senior", hours: "8" }] }] });
    await openEditor(page, ce.id);
    await page.getByRole("button", { name: "+ Aggiungi una riga a questa fase" }).click();
    await row(page, "Profilo", 2).selectOption("");
    await row(page, "Collaboratore", 2).selectOption({ label: "Ferri Luca" });
    await expect(row(page, "Profilo", 2).locator("option:checked")).toHaveText("Specialist");
  });

  test("incolla da Excel: una colonna di ore riempie le righe", async ({ page }) => {
    const lines = ["A", "B", "C"].map((activity) => ({ activity, profile: "Senior", hours: "0" }));
    const ce = await createCe(page, { phases: [{ name: "Delivery", lines }] });
    await openEditor(page, ce.id);
    await row(page, "Ore").evaluate((el, text) => {
      const data = new DataTransfer();
      data.setData("text/plain", text);
      el.dispatchEvent(new ClipboardEvent("paste", { clipboardData: data, bubbles: true, cancelable: true }));
    }, "8\n16\n24,5\n");
    await expect(row(page, "Ore", 1)).toHaveValue("8");
    await expect(row(page, "Ore", 2)).toHaveValue("16");
    await expect(row(page, "Ore", 3)).toHaveValue("24,5");
    await expect(PREVIEW(page)).toContainText("6,06"); // (8 + 16 + 24,5) ore = 6,0625 giornate
  });

  test("Invio scende alla riga sotto nella stessa colonna", async ({ page }) => {
    const lines = ["A", "B"].map((activity) => ({ activity, profile: "Senior", hours: "8" }));
    const ce = await createCe(page, { phases: [{ name: "Delivery", lines }] });
    await openEditor(page, ce.id);
    await row(page, "Ore", 1).focus();
    await page.keyboard.press("Enter");
    await expect(row(page, "Ore", 2)).toBeFocused();
    await page.keyboard.press("Shift+Enter");
    await expect(row(page, "Ore", 1)).toBeFocused();
  });

  test("righe e fasi: sposta, duplica, elimina", async ({ page }) => {
    const ce = await createCe(page, { phases: [{ name: "Delivery", lines: [{ activity: "Prima", profile: "Senior", hours: "8" }, { activity: "Seconda", profile: "Senior", hours: "16" }] }] });
    await openEditor(page, ce.id);
    await page.getByRole("button", { name: /Azioni della riga 2 della fase Delivery/ }).click();
    await page.getByRole("menuitem", { name: "Sposta su" }).click();
    await expect(row(page, "Attività", 1)).toHaveValue("Seconda");
    await page.getByRole("button", { name: /Azioni della riga 1 della fase Delivery/ }).click();
    await page.getByRole("menuitem", { name: "Duplica la riga" }).click();
    await expect(row(page, "Attività", 2)).toHaveValue("Seconda");
    await page.getByRole("button", { name: /Azioni della riga 3 della fase Delivery/ }).click();
    await page.getByRole("menuitem", { name: "Elimina la riga" }).click();
    await expect(row(page, "Attività", 3)).toHaveCount(0);
    await page.getByRole("button", { name: "+ Aggiungi una fase" }).click();
    await expect(page.getByRole("region", { name: /^Fase \d$/ })).toHaveCount(2);
    await page.getByRole("button", { name: /Azioni della fase Delivery/ }).click();
    await page.getByRole("menuitem", { name: "Elimina la fase" }).click();
    await page.getByRole("dialog").getByRole("button", { name: "Elimina la fase" }).click();
    await expect(page.getByRole("region", { name: /^Fase \d$/ })).toHaveCount(1);
  });

  test("annulla modifiche riporta allo stato salvato", async ({ page }) => {
    const ce = await createCe(page, { phases: ONE_LINE });
    await openEditor(page, ce.id);
    await row(page, "Ore").fill("99");
    await expect(page.getByText("Modifiche non salvate")).toBeVisible();
    await page.getByRole("button", { name: "Annulla modifiche" }).click();
    await expect(row(page, "Ore")).toHaveValue("16");
    await expect(page.getByText("Tutto salvato")).toBeVisible();
  });

  test("prima di salvare spiega cosa correggere", async ({ page }) => {
    const ce = await createCe(page, { phases: ONE_LINE });
    await openEditor(page, ce.id);
    await page.getByRole("button", { name: "+ Aggiungi una riga a questa fase" }).click();
    await row(page, "Profilo", 2).selectOption(""); // la riga nuova riprende il profilo dell'ultima: lo togliamo
    await row(page, "Ore", 2).fill("tanto");
    await page.getByRole("button", { name: "Salva" }).click();
    const alert = page.getByRole("alert").filter({ hasText: "Prima di salvare" });
    await expect(alert).toContainText("riga 2: manca l'attività");
    await expect(alert).toContainText("riga 2: scegli il profilo");
    await expect(alert).toContainText("riga 2: ore, inserisci un numero");
    await expect(PREVIEW(page)).toContainText("Completa i dati");
  });

  test("avvisa se si esce con modifiche non salvate", async ({ page }) => {
    const ce = await createCe(page, { phases: ONE_LINE });
    await openEditor(page, ce.id);
    await row(page, "Ore").fill("40");
    await page.getByRole("link", { name: "← Torna al dettaglio" }).click();
    const dialog = page.getByRole("dialog", { name: "Modifiche non salvate" });
    await expect(dialog).toBeVisible();
    await dialog.getByRole("button", { name: "Resta qui" }).click();
    await expect(page).toHaveURL(/\/modifica$/);
    await expect(row(page, "Ore")).toHaveValue("40");
    await page.getByRole("link", { name: "← Torna al dettaglio" }).click();
    await page.getByRole("dialog").getByRole("button", { name: "Esci senza salvare" }).click();
    await expect(page).toHaveURL(new RegExp(`/ce/${ce.id}$`));
    await page.goto(`/ce/${ce.id}/modifica`);
    await expect(row(page, "Ore")).toHaveValue("16"); // la modifica non era stata salvata
  });

  test("senza modifiche si esce senza avvisi", async ({ page }) => {
    const ce = await createCe(page, { phases: ONE_LINE });
    await openEditor(page, ce.id);
    await page.getByRole("link", { name: "← Torna al dettaglio" }).click();
    await expect(page).toHaveURL(new RegExp(`/ce/${ce.id}$`));
  });

  test("conflitto: se qualcuno modifica nel frattempo, non si sovrascrive nulla", async ({ page }) => {
    const ce = await createCe(page, { phases: ONE_LINE });
    await openEditor(page, ce.id);
    await row(page, "Ore").fill("24");
    // un'altra persona (l'amministratore) salva nel frattempo
    await putContent(page, { ...ce, phases: [{ name: "Delivery", lines: [{ activity: "Sviluppo", profile: "Senior", hours: "80" }] }], by: ADMIN });
    await page.getByRole("button", { name: "Salva" }).click();
    await expect(page.getByRole("alert").filter({ hasText: "modificato da qualcun altro" })).toBeVisible();
    // nulla è stato sovrascritto
    const server = await api(page, ADMIN, "GET", `/api/v1/ce/${ce.id}`);
    expect(server.json.phases[0].lines[0].hours).toBe("80.00");
    await page.getByRole("button", { name: "Ricarica l'ultima versione" }).click();
    await expect(row(page, "Ore")).toHaveValue("80");
    await expect(page.getByText("Tutto salvato")).toBeVisible();
  });
});

test.describe("editor a percentuali", () => {
  const alloc = { "2026-03-01": "50", "2026-04-01": "100" };
  const phases = [{ name: "Allocazione", lines: [{ activity: "Sviluppo", profile: "Senior", alloc }] }];

  test("mostra una colonna per mese e calcola i giorni dalla % e dai giorni lavorativi", async ({ page }) => {
    const ce = await createCe(page, { mode: "percent", phases });
    await openEditor(page, ce.id);
    for (const mese of ["MAR 2026", "APR 2026", "MAG 2026"]) await expect(page.getByRole("columnheader", { name: mese })).toBeVisible();
    await page.locator("details", { hasText: "Giorni non lavorativi per mese" }).locator("summary").click();
    const workdays = async (label: string) => Number((await page.locator("div", { has: page.getByLabel(label, { exact: true }) }).last().innerText()).match(/(\d+) lavorativi/)![1]);
    const [mar, apr] = [await workdays("mar 2026"), await workdays("apr 2026")];
    const expected = (0.5 * mar + 1 * apr).toFixed(2).replace(".", ",");
    await expect(page.getByRole("region", { name: "Righe della fase Allocazione" }).locator("tbody tr").first()).toContainText(expected, { timeout: 8000 });
  });

  test("modificare una percentuale e incollare un blocco da Excel", async ({ page }) => {
    const two = [{ name: "Allocazione", lines: [{ activity: "A", profile: "Senior", alloc }, { activity: "B", profile: "Senior", alloc: {} }] }];
    const ce = await createCe(page, { mode: "percent", phases: two });
    await openEditor(page, ce.id);
    const cell = (n: number, mese: string) => page.getByLabel(`Percentuale di ${mese}, riga ${n} della fase Allocazione`);
    await expect(cell(1, "mar 2026")).toHaveValue("50");
    await cell(2, "mar 2026").evaluate((el, text) => {
      const data = new DataTransfer();
      data.setData("text/plain", text);
      el.dispatchEvent(new ClipboardEvent("paste", { clipboardData: data, bubbles: true, cancelable: true }));
    }, "10\t20\t30\n40%\t50%\t60%");
    await expect(cell(2, "mar 2026")).toHaveValue("10");
    await expect(cell(2, "apr 2026")).toHaveValue("20");
    await expect(cell(2, "mag 2026")).toHaveValue("30");
    await page.getByRole("button", { name: "Salva" }).click();
    await expect(page.getByText(/Modifiche salvate/)).toBeVisible();
    const server = await api(page, PRESALE, "GET", `/api/v1/ce/${ce.id}`);
    expect(server.json.phases[0].lines[1].allocations.map((a: { pct: string }) => a.pct)).toEqual(["10.00", "20.00", "30.00"]);
  });

  test("una percentuale oltre il 100% è segnalata", async ({ page }) => {
    const ce = await createCe(page, { mode: "percent", phases });
    await openEditor(page, ce.id);
    await page.getByLabel("Percentuale di mar 2026, riga 1 della fase Allocazione").fill("150");
    await page.getByRole("button", { name: "Salva" }).click();
    await expect(page.getByRole("alert").filter({ hasText: "Prima di salvare" })).toContainText("percentuale, al massimo 100");
  });
});

test.describe("flusso di approvazione", () => {
  const detailBadge = (page: Page, text: string) => expect(page.locator("main").getByText(text, { exact: true }).first()).toBeVisible();
  const confirm = (page: Page, name: string) => page.getByRole("dialog").getByRole("button", { name }).click();

  test("invio, approvazione, nuova versione e scarto", async ({ page }) => {
    const ce = await createCe(page, { phases: ONE_LINE });
    await loginAs(page, PRESALE);
    await page.goto(`/ce/${ce.id}`);
    await page.getByRole("button", { name: "Invia in approvazione" }).click();
    await confirm(page, "Invia in approvazione");
    await detailBadge(page, "In approvazione");
    await expect(page.getByRole("link", { name: "Modifica" })).toHaveCount(0); // in approvazione non si modifica
    await expect(page.getByRole("button", { name: "Ritira" })).toBeVisible();
    // l'amministratore approva
    await page.evaluate(() => sessionStorage.clear());
    await loginAs(page, ADMIN);
    await page.goto(`/ce/${ce.id}`);
    await page.getByRole("button", { name: "Approva", exact: true }).click();
    await confirm(page, "Approva");
    await detailBadge(page, "Approvato");
    await expect(page.getByRole("button", { name: "Nuova versione" })).toBeVisible();
    // il presale crea una nuova versione, entra in modifica e poi la scarta
    await page.evaluate(() => sessionStorage.clear());
    await loginAs(page, PRESALE);
    await page.goto(`/ce/${ce.id}`);
    await page.getByRole("button", { name: "Nuova versione" }).click();
    await confirm(page, "Crea la versione");
    await expect(page).toHaveURL(new RegExp(`/ce/${ce.id}/modifica$`));
    await expect(page.getByText("v2", { exact: true })).toBeVisible();
    await page.getByRole("link", { name: "← Torna al dettaglio" }).click();
    await page.getByRole("button", { name: "Altre azioni" }).click();
    await page.getByRole("menuitem", { name: "Scarta la versione in lavorazione" }).click();
    await confirm(page, "Scarta la versione");
    await detailBadge(page, "Approvato");
    await expect(page.getByText("v1", { exact: true })).toBeVisible();
  });

  test("rifiuto con motivo, correzione e nuovo invio", async ({ page }) => {
    const ce = await createCe(page, { phases: ONE_LINE });
    await api(page, PRESALE, "POST", `/api/v1/ce/${ce.id}/submit`);
    await loginAs(page, ADMIN);
    await page.goto(`/ce/${ce.id}`);
    await page.getByRole("button", { name: "Rifiuta", exact: true }).click();
    const reject = page.getByRole("dialog").getByRole("button", { name: "Rifiuta" });
    await expect(reject).toBeDisabled(); // il motivo è obbligatorio
    await page.getByLabel("Motivo del rifiuto").fill("Servono più ore di test");
    await reject.click();
    await detailBadge(page, "Rifiutato");
    await page.evaluate(() => sessionStorage.clear());
    await loginAs(page, PRESALE);
    await page.goto(`/ce/${ce.id}`);
    await expect(page.getByRole("alert")).toContainText("Servono più ore di test");
    await page.getByRole("link", { name: "Modifica" }).click();
    await row(page, "Ore").fill("40");
    await page.getByRole("button", { name: "Salva" }).click();
    await expect(page.getByText(/Modifiche salvate/)).toBeVisible();
    await page.getByRole("link", { name: "← Torna al dettaglio" }).click();
    await page.getByRole("button", { name: "Invia in approvazione" }).click();
    await confirm(page, "Invia in approvazione");
    await detailBadge(page, "In approvazione");
  });

  test("un CE incompleto non si invia e il motivo è elencato", async ({ page }) => {
    const ce = await createCe(page, { phases: [{ name: "Delivery", lines: [] }] });
    await loginAs(page, PRESALE);
    await page.goto(`/ce/${ce.id}`);
    await page.getByRole("button", { name: "Invia in approvazione" }).click();
    await confirm(page, "Invia in approvazione");
    await expect(page.getByRole("dialog").getByRole("alert")).toBeVisible();
    await expect(page.getByRole("dialog")).toContainText(/riga|ore|vuoto|completo/i);
    await page.getByRole("dialog").getByRole("button", { name: "Annulla" }).click();
    await detailBadge(page, "Bozza");
  });

  test("ritiro dall'approvazione", async ({ page }) => {
    const ce = await createCe(page, { phases: ONE_LINE });
    await api(page, PRESALE, "POST", `/api/v1/ce/${ce.id}/submit`);
    await loginAs(page, PRESALE);
    await page.goto(`/ce/${ce.id}`);
    await page.getByRole("button", { name: "Ritira" }).click();
    await confirm(page, "Ritira");
    await detailBadge(page, "Bozza");
    await expect(page.getByRole("link", { name: "Modifica" })).toBeVisible();
  });

  test("duplica come nuovo CE", async ({ page }) => {
    const ce = await createCe(page, { phases: ONE_LINE });
    await loginAs(page, PRESALE);
    await page.goto(`/ce/${ce.id}`);
    await page.getByRole("button", { name: "Altre azioni" }).click();
    await page.getByRole("menuitem", { name: "Duplica come nuovo CE" }).click();
    const copy = uniqueCode("PS-E2E-COPIA");
    await page.getByLabel("Codice del nuovo CE").fill(copy);
    await page.getByRole("button", { name: "Crea il duplicato" }).click();
    await expect(page).toHaveURL(/\/ce\/[0-9a-f-]+\/modifica$/);
    track(page.url().match(/\/ce\/([0-9a-f-]+)\//)![1]);
    await expect(page.getByRole("heading", { name: copy, level: 1 })).toBeVisible();
    await expect(row(page, "Attività")).toHaveValue("Sviluppo");
    await expect(row(page, "Ore")).toHaveValue("16");
  });

  test("creare un cliente dentro la finestra «Duplica» non crea un CE per sbaglio", async ({ page }) => {
    const ce = await createCe(page, { phases: ONE_LINE });
    await loginAs(page, PRESALE);
    await page.goto(`/ce/${ce.id}`);
    await page.getByRole("button", { name: "Altre azioni" }).click();
    await page.getByRole("menuitem", { name: "Duplica come nuovo CE" }).click();
    const copy = uniqueCode("PS-E2E-NONCREARE");
    await page.getByLabel("Codice del nuovo CE").fill(copy); // il modulo sarebbe già valido e inviabile
    await page.getByRole("button", { name: "+ Nuovo" }).click();
    await page.getByLabel("Nome del cliente").fill(`Cliente duplica ${Date.now().toString(36)}`);
    await page.getByRole("button", { name: "Crea cliente" }).click();
    await expect(page.getByRole("dialog", { name: "Nuovo cliente" })).toBeHidden();
    await expect(page).toHaveURL(new RegExp(`/ce/${ce.id}$`)); // siamo ancora qui: nessun duplicato creato
    const found = await api(page, ADMIN, "GET", `/api/v1/ce?code=${copy}`);
    expect(found.json.total).toBe(0);
    await expect(page.getByLabel("Codice del nuovo CE")).toHaveValue(copy);
  });

  test("solo l'amministratore elimina un CE", async ({ page }) => {
    const ce = await createCe(page, { phases: ONE_LINE });
    await loginAs(page, PRESALE);
    await page.goto(`/ce/${ce.id}`);
    await page.getByRole("button", { name: "Altre azioni" }).click();
    await expect(page.getByRole("menuitem", { name: "Elimina il CE" })).toHaveCount(0);
    await page.keyboard.press("Escape");
    await page.evaluate(() => sessionStorage.clear());
    await loginAs(page, ADMIN);
    await page.goto(`/ce/${ce.id}`);
    await page.getByRole("button", { name: "Altre azioni" }).click();
    await page.getByRole("menuitem", { name: "Elimina il CE" }).click();
    await page.getByRole("dialog").getByRole("button", { name: "Elimina" }).click();
    await expect(page).toHaveURL(/\/ce$/);
    await page.goto(`/ce?code=${ce.code}`);
    await expect(page.getByRole("heading", { name: "Nessun risultato" })).toBeVisible();
  });
});

test.describe("permessi", () => {
  test("il viewer non ha i pulsanti di modifica né può aprire le pagine di modifica", async ({ page }) => {
    await loginAs(page, VIEWER);
    await expect(page.getByRole("link", { name: "+ Nuovo CE" })).toHaveCount(0);
    await page.getByRole("link", { name: /PS-ALFA-ECOM-PJT/ }).first().click();
    await expect(page.getByRole("link", { name: "Modifica" })).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Altre azioni" })).toHaveCount(0);
    await page.goto("/ce/nuovo");
    await expect(page.getByRole("alert")).toContainText("Non hai i permessi");
    await page.goto("/ce/00000000-0000-0000-0000-000000000000/modifica");
    await expect(page.getByRole("alert")).toContainText("Non hai i permessi");
  });

  test("un presale non modifica il CE di un collega e il messaggio dice perché", async ({ page }) => {
    const ce = await createCe(page, { phases: ONE_LINE, by: PRESALE });
    await loginAs(page, "paolo.presale@huware.com");
    await page.goto(`/ce/${ce.id}`);
    await expect(page.getByRole("link", { name: "Modifica" })).toHaveCount(0);
    await page.goto(`/ce/${ce.id}/modifica`);
    await expect(page.getByText(/solo l'autore/i)).toBeVisible();
    await expect(page.getByRole("heading", { name: "Fasi e righe" })).toHaveCount(0);
  });

  test("un CE approvato non si apre in modifica", async ({ page }) => {
    const ce = await createCe(page, { phases: ONE_LINE });
    await api(page, PRESALE, "POST", `/api/v1/ce/${ce.id}/submit`);
    await api(page, ADMIN, "POST", `/api/v1/ce/${ce.id}/approve`);
    await loginAs(page, PRESALE);
    await page.goto(`/ce/${ce.id}/modifica`);
    await expect(page.getByText(/È approvata/)).toBeVisible();
  });
});

test.describe("schermo piccolo", () => {
  test.skip(({ isMobile }) => !isMobile, "solo smartphone");
  test("editor e modulo non fanno scorrere la pagina in orizzontale", async ({ page }) => {
    const ce = await createCe(page, { phases: ONE_LINE });
    await openEditor(page, ce.id);
    await expectNoPageOverflow(page);
    await page.goto("/ce/nuovo");
    await expectNoPageOverflow(page);
  });

  test("anche l'editor a percentuali (tante colonne) resta nella larghezza dello schermo e i pulsanti si possono toccare", async ({ page }) => {
    const alloc = Object.fromEntries(["2026-01-01", "2026-02-01", "2026-03-01", "2026-04-01", "2026-05-01", "2026-06-01", "2026-07-01", "2026-08-01"].map((m) => [m, "50"]));
    const ce = await createCe(page, { mode: "percent", start: "2026-01-12", end: "2026-08-28", phases: [{ name: "Allocazione", lines: [{ activity: "Sviluppo", profile: "Senior", alloc }] }] });
    await openEditor(page, ce.id);
    await expectNoPageOverflow(page);
    await page.getByLabel("Percentuale di gen 2026, riga 1 della fase Allocazione").fill("60");
    for (const name of ["Annulla modifiche", "Salva"]) {
      const box = await page.getByRole("button", { name }).boundingBox();
      expect(box!.x + box!.width, `«${name}» deve stare dentro lo schermo`).toBeLessThanOrEqual(391);
      expect(box!.height).toBeGreaterThanOrEqual(36);
    }
    await page.getByRole("button", { name: "Annulla modifiche" }).click(); // con un tocco vero, non forzato
    await expect(page.getByLabel("Percentuale di gen 2026, riga 1 della fase Allocazione")).toHaveValue("50");
  });
});
