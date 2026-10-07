import { expect, test, type Page } from "@playwright/test";

import { ADMIN, PRESALE, VIEWER, api, cleanup, createCe, expectNoPageOverflow, loginAs, track } from "./helpers";

const uniq = () => `${Date.now().toString(36)}${Math.floor(Math.random() * 900 + 100)}`;
const dialog = (page: Page) => page.getByRole("dialog");
const notice = (page: Page) => page.getByRole("status");

// Ciò che i test creano e non si può eliminare (utenti, clienti, collaboratori, profili) viene disattivato a fine test.
const toDeactivate: { path: string; q: string; patch: string }[] = [];
const days: string[] = [];
test.afterEach(async ({ page }) => {
  await cleanup(page);
  while (toDeactivate.length) {
    const { path, q, patch } = toDeactivate.pop()!;
    const found = await api(page, ADMIN, "GET", `${path}?q=${encodeURIComponent(q)}&limit=200`);
    for (const item of found.json.items ?? found.json) if ((item.email ?? item.name ?? `${item.last_name}`).toString().includes(q) || JSON.stringify(item).includes(q)) await api(page, ADMIN, "PATCH", `${path}/${item.id}`, { is_active: false }).catch(() => {});
    void patch;
  }
  while (days.length) {
    const year = days.pop()!;
    const list = await api(page, ADMIN, "GET", `/api/v1/calendar?year=${year}`);
    for (const d of list.json) await api(page, ADMIN, "DELETE", `/api/v1/calendar/${d.id}`);
  }
});

test.describe("accesso riservato agli amministratori", () => {
  for (const [who, email] of [["presale", PRESALE], ["viewer", VIEWER]] as const) {
    test(`il ${who} non ha la voce nel menu, le pagine sono negate e l'API risponde 403`, async ({ page }) => {
      await loginAs(page, email);
      await expect(page.getByRole("link", { name: "Amministrazione" })).toHaveCount(0);
      await page.goto("/admin/utenti");
      await expect(page.getByRole("alert")).toContainText("riservata agli amministratori");
      expect((await api(page, email, "GET", "/api/v1/users")).status).toBe(403);
      expect((await api(page, email, "POST", "/api/v1/clients", { name: "Non dovrei" })).status === 201 && who === "viewer").toBe(false);
    });
  }
  test("l'amministratore vede la voce e le sette schede", async ({ page, isMobile }) => {
    await loginAs(page, ADMIN);
    if (isMobile) await page.getByRole("button", { name: "Menu" }).click();
    await page.getByRole("navigation", { name: isMobile ? "Principale mobile" : "Principale" }).getByRole("link", { name: "Amministrazione" }).click();
    await expect(page).toHaveURL(/\/admin\/utenti$/);
    const tabs = page.getByRole("navigation", { name: "Amministrazione" });
    for (const t of ["Utenti", "Clienti", "Collaboratori", "Listino", "Calendario", "Email", "CE eliminati"]) await expect(tabs.getByRole("link", { name: t })).toBeVisible();
  });
});

test.describe("utenti", () => {
  test.beforeEach(async ({ page }) => loginAs(page, ADMIN));

  test("crea, modifica il ruolo e disattiva un utente", async ({ page }) => {
    const id = uniq();
    const email = `e2e.${id}@huware.com`;
    toDeactivate.push({ path: "/api/v1/users", q: email, patch: "" });
    await page.goto("/admin/utenti");
    await page.getByRole("button", { name: "+ Nuovo utente" }).click();
    await dialog(page).getByLabel("Email aziendale").fill(email);
    await dialog(page).getByLabel("Nome e cognome").fill(`Prova ${id}`);
    await dialog(page).getByLabel("Ruolo").selectOption({ label: "Viewer" });
    await dialog(page).getByRole("button", { name: "Crea l'utente" }).click();
    await expect(notice(page)).toContainText(`Utente creato: Prova ${id}`);
    await page.getByLabel("Cerca per nome o email").fill(email);
    const row = page.getByRole("row").filter({ hasText: email });
    await expect(row).toContainText("Viewer");
    await expect(row).toContainText("Mai"); // non ha ancora fatto accesso
    await row.getByRole("button", { name: /Modifica/ }).click();
    await dialog(page).getByLabel("Ruolo").selectOption({ label: "Presale" });
    await dialog(page).getByRole("button", { name: "Salva" }).click();
    await expect(row).toContainText("Presale");
    await row.getByRole("button", { name: /Modifica/ }).click();
    await dialog(page).getByLabel("Può accedere al portale").uncheck();
    await dialog(page).getByRole("button", { name: "Salva" }).click();
    await expect(row).toContainText("Disattivato");
    // un utente disattivato non può più entrare
    await page.evaluate(() => sessionStorage.clear());
    await page.goto("/login");
    await page.getByLabel("Email di un utente registrato").fill(email);
    await page.getByRole("button", { name: "Entra senza Google" }).click();
    await expect(page.getByRole("alert")).toBeVisible();
    await expect(page).toHaveURL(/\/login$/);
  });

  test("errori chiari: email già registrata e dominio non ammesso", async ({ page }) => {
    await page.goto("/admin/utenti");
    for (const [email, expected] of [[ADMIN, /già|esiste|registrat/i], ["qualcuno@gmail.com", /dominio|non ammess|consentit/i]] as const) {
      await page.getByRole("button", { name: "+ Nuovo utente" }).click();
      await dialog(page).getByLabel("Email aziendale").fill(email);
      await dialog(page).getByLabel("Nome e cognome").fill("Prova errore");
      await dialog(page).getByRole("button", { name: "Crea l'utente" }).click();
      await expect(dialog(page).getByRole("alert")).toContainText(expected);
      await dialog(page).getByRole("button", { name: "Annulla" }).click();
    }
  });

  test("non si può togliere il ruolo all'ultimo amministratore", async ({ page }) => {
    const admins = await api(page, ADMIN, "GET", "/api/v1/users?role=admin&is_active=true&limit=200");
    test.skip(admins.json.total !== 1, "il database ha più di un amministratore attivo");
    await page.goto("/admin/utenti");
    await page.getByRole("row").filter({ hasText: ADMIN }).getByRole("button", { name: /Modifica/ }).click();
    await dialog(page).getByLabel("Ruolo").selectOption({ label: "Presale" });
    await dialog(page).getByRole("button", { name: "Salva" }).click();
    await expect(dialog(page).getByRole("alert")).toContainText(/almeno un amministratore/i);
  });

  test("i filtri riducono l'elenco", async ({ page }) => {
    await page.goto("/admin/utenti");
    await page.getByLabel("Ruolo", { exact: true }).selectOption({ label: "Viewer" });
    await expect(page.getByRole("row").filter({ hasText: "vera.viewer@huware.com" })).toBeVisible();
    await expect(page.getByRole("row").filter({ hasText: "anna.presale@huware.com" })).toHaveCount(0);
    await page.getByLabel("Ruolo", { exact: true }).selectOption("");
    await page.getByLabel("Cerca per nome o email").fill("paolo");
    await expect(page.getByRole("row").filter({ hasText: "paolo.presale@huware.com" })).toBeVisible();
    await expect(page.getByRole("row").filter({ hasText: "anna.presale@huware.com" })).toHaveCount(0);
  });
});

test.describe("clienti", () => {
  test.beforeEach(async ({ page }) => loginAs(page, ADMIN));

  test("crea, modifica e disattiva: un cliente disattivato esce dalle scelte", async ({ page }) => {
    const name = `Cliente E2E ${uniq()}`;
    toDeactivate.push({ path: "/api/v1/clients", q: name, patch: "" });
    await page.goto("/admin/clienti");
    await page.getByRole("button", { name: "+ Nuovo cliente" }).click();
    await dialog(page).getByLabel("Nome del cliente").fill(name);
    await dialog(page).getByLabel("Indirizzo (facoltativo)").fill("Via Roma 1, Milano");
    await dialog(page).getByRole("button", { name: "Crea il cliente" }).click();
    await expect(notice(page)).toContainText(`Cliente creato: ${name}`);
    await page.getByLabel("Cerca per nome").fill(name);
    const row = page.getByRole("row").filter({ hasText: name });
    await expect(row).toContainText("Via Roma 1");
    await row.getByRole("button", { name: /Modifica/ }).click();
    await dialog(page).getByLabel("Riferimento esterno (facoltativo)").fill("NS-123");
    await dialog(page).getByRole("button", { name: "Salva" }).click();
    await expect(row).toContainText("NS-123");
    // si sceglie nei nuovi CE
    await page.goto("/ce/nuovo");
    await expect(page.getByLabel("Cliente", { exact: true }).locator("option", { hasText: name })).toHaveCount(1);
    await page.goto("/admin/clienti");
    await page.getByLabel("Cerca per nome").fill(name);
    await row.getByRole("button", { name: /Modifica/ }).click();
    await dialog(page).getByLabel("Cliente attivo").uncheck();
    await dialog(page).getByRole("button", { name: "Salva" }).click();
    await expect(row).toContainText("Disattivato");
    await page.goto("/ce/nuovo");
    await expect(page.getByLabel("Cliente", { exact: true }).locator("option", { hasText: name })).toHaveCount(0);
  });

  test("un nome già usato è rifiutato", async ({ page }) => {
    await page.goto("/admin/clienti");
    await page.getByRole("button", { name: "+ Nuovo cliente" }).click();
    await dialog(page).getByLabel("Nome del cliente").fill("alfa retail"); // senza distinzione di maiuscole
    await dialog(page).getByRole("button", { name: "Crea il cliente" }).click();
    await expect(dialog(page).getByRole("alert")).toContainText(/già un cliente|esiste/i);
  });
});

test.describe("collaboratori", () => {
  test.beforeEach(async ({ page }) => loginAs(page, ADMIN));

  test("crea e modifica un collaboratore", async ({ page }) => {
    const last = `E2E${uniq()}`;
    toDeactivate.push({ path: "/api/v1/employees", q: last, patch: "" });
    await page.goto("/admin/collaboratori");
    await page.getByRole("button", { name: "+ Nuovo collaboratore" }).click();
    await expect(dialog(page).getByRole("button", { name: "Crea il collaboratore" })).toBeDisabled(); // mancano i dati
    await dialog(page).getByLabel("Nome", { exact: true }).fill("Prova");
    await dialog(page).getByLabel("Cognome").fill(last);
    await dialog(page).getByLabel("Profilo di default").selectOption({ label: "Senior" });
    await dialog(page).getByRole("button", { name: "Crea il collaboratore" }).click();
    await expect(notice(page)).toContainText(`Collaboratore creato: Prova ${last}`);
    await page.getByLabel("Cerca per nome").fill(last);
    const row = page.getByRole("row").filter({ hasText: last });
    await expect(row).toContainText("Senior");
    await row.getByRole("button", { name: /Modifica/ }).click();
    await dialog(page).getByLabel("ID NetSuite (facoltativo)").fill("NS-42");
    await dialog(page).getByLabel("Profilo di default").selectOption({ label: "Specialist" });
    await dialog(page).getByRole("button", { name: "Salva" }).click();
    await expect(row).toContainText("NS-42");
    await expect(row).toContainText("Specialist");
  });

  test("importazione da CSV: prima il controllo (errori per riga), poi la conferma", async ({ page }) => {
    const last = `Csv${uniq()}`;
    toDeactivate.push({ path: "/api/v1/employees", q: last, patch: "" });
    await page.goto("/admin/collaboratori");
    await page.getByRole("button", { name: "Importa da CSV" }).click();
    const csv = (rows: string) => ({ name: "collaboratori.csv", mimeType: "text/csv", buffer: Buffer.from(`Nome;Cognome;Profilo;Attivo\n${rows}`) });
    await dialog(page).getByLabel("File CSV").setInputFiles(csv(`Mario;${last};Senior;sì\nAnna;Verdi;ProfiloInesistente;sì\n;Neri;Senior;sì\n`));
    await dialog(page).getByRole("button", { name: "Controlla il file" }).click();
    const errors = dialog(page).getByRole("alert");
    await expect(errors).toContainText("2 errori: non è stato importato nulla");
    await expect(errors).toContainText("Riga 3");
    await expect(errors).toContainText("ProfiloInesistente");
    await expect(dialog(page).getByRole("button", { name: "Importa" })).toHaveCount(0);
    const none = await api(page, ADMIN, "GET", `/api/v1/employees?q=${last}`);
    expect(none.json.total).toBe(0); // tutto o niente: nemmeno la riga corretta è stata importata
    await dialog(page).getByLabel("File CSV").setInputFiles(csv(`Mario;${last};Senior;sì\n`));
    await dialog(page).getByRole("button", { name: "Controlla il file" }).click();
    await expect(dialog(page).getByRole("status")).toContainText("1 nuovo");
    expect((await api(page, ADMIN, "GET", `/api/v1/employees?q=${last}`)).json.total).toBe(0); // il controllo non scrive
    await dialog(page).getByRole("button", { name: "Importa" }).click();
    await expect(dialog(page)).toContainText("Importazione completata");
    await dialog(page).getByRole("button", { name: "Chiudi" }).click();
    await page.getByLabel("Cerca per nome").fill(last);
    await expect(page.getByRole("row").filter({ hasText: last })).toContainText("Senior");
  });
});

test.describe("listino", () => {
  test.beforeEach(async ({ page }) => loginAs(page, ADMIN));

  test("le tariffe 2026 coincidono con il listino", async ({ page }) => {
    await page.goto("/admin/listino");
    await expect(page.getByLabel("Anno delle tariffe")).toHaveValue("2026");
    const row = page.getByRole("row").filter({ has: page.getByRole("rowheader", { name: /^Senior/ }) });
    await expect(row).toContainText("850,00 €");
    await expect(row).toContainText("330,00 €");
    await expect(row).toContainText("61,18%");
    await expect(page.getByRole("row").filter({ has: page.getByRole("rowheader", { name: /Esterni/ }) })).toContainText("esterno");
  });

  test("nuovo profilo, tariffa con virgola italiana, modifica ed eliminazione", async ({ page }) => {
    const name = `Profilo E2E ${uniq()}`;
    toDeactivate.push({ path: "/api/v1/profiles", q: name, patch: "" });
    await page.goto("/admin/listino?anno=2026");
    await page.getByRole("button", { name: "+ Nuovo profilo" }).click();
    await dialog(page).getByLabel("Nome del profilo").fill(name);
    await dialog(page).getByLabel("Fascia").fill("X1");
    await dialog(page).getByRole("button", { name: "Crea il profilo" }).click();
    await expect(notice(page)).toContainText(`Profilo creato: ${name}`);
    const row = page.getByRole("row").filter({ has: page.getByRole("rowheader", { name: new RegExp(name) }) });
    await expect(row).toContainText("nessuna tariffa");
    await row.getByRole("button", { name: /Tariffa 2026/ }).click();
    await expect(dialog(page).getByRole("button", { name: "Salva la tariffa" })).toBeDisabled();
    await dialog(page).getByLabel("Prezzo al giorno (€)").fill("1.234,5");
    await dialog(page).getByLabel("Costo al giorno (€)").fill("500");
    await dialog(page).getByRole("button", { name: "Salva la tariffa" }).click();
    await expect(row).toContainText("1.234,50 €");
    await expect(row).toContainText("59,50%"); // (1234,5-500)/1234,5 = 59,498%
    await row.getByRole("button", { name: /Tariffa 2026/ }).click();
    await dialog(page).getByLabel("Prezzo al giorno (€)").fill("1000");
    await dialog(page).getByRole("button", { name: "Salva la tariffa" }).click();
    await expect(row).toContainText("1.000,00 €");
    await expect(row).toContainText("50,00%");
    await row.getByRole("button", { name: /Tariffa 2026/ }).click();
    await dialog(page).getByRole("button", { name: "Elimina la tariffa 2026" }).click();
    await expect(row).toContainText("nessuna tariffa");
  });

  test("valori non validi: il pulsante resta spento e l'errore è scritto", async ({ page }) => {
    await page.goto("/admin/listino");
    await page.getByRole("row").filter({ has: page.getByRole("rowheader", { name: /^Senior/ }) }).getByRole("button", { name: /Tariffa 2026/ }).click();
    await dialog(page).getByLabel("Prezzo al giorno (€)").fill("molto");
    await expect(dialog(page).getByText("Inserisci un numero")).toBeVisible();
    await expect(dialog(page).getByRole("button", { name: "Salva la tariffa" })).toBeDisabled();
    await dialog(page).getByLabel("Prezzo al giorno (€)").fill("850,255");
    await expect(dialog(page).getByText("Al massimo 2 decimali")).toBeVisible();
  });

  test("importazione del listino: errori per riga e nulla scritto", async ({ page }) => {
    const name = `Importato ${uniq()}`;
    toDeactivate.push({ path: "/api/v1/profiles", q: name, patch: "" });
    await page.goto("/admin/listino");
    await page.getByRole("button", { name: "Importa il listino da CSV" }).click();
    const csv = (rows: string) => ({ name: "listino.csv", mimeType: "text/csv", buffer: Buffer.from(`Profilo;Anno;Prezzo giorno;Costo giorno\n${rows}`) });
    await dialog(page).getByLabel("File CSV").setInputFiles(csv(`${name};2026;1.000,00;abc\n`));
    await dialog(page).getByRole("button", { name: "Controlla il file" }).click();
    await expect(dialog(page).getByRole("alert")).toContainText("Riga 2");
    await dialog(page).getByLabel("File CSV").setInputFiles(csv(`${name};2026;1.000,00;400,00\n`));
    await dialog(page).getByRole("button", { name: "Controlla il file" }).click();
    await expect(dialog(page).getByRole("status")).toContainText("1 nuovo");
    await dialog(page).getByRole("button", { name: "Importa" }).click();
    await expect(dialog(page)).toContainText("Importazione completata");
    await dialog(page).getByRole("button", { name: "Chiudi" }).click();
    await expect(page.getByRole("row").filter({ has: page.getByRole("rowheader", { name: new RegExp(name) }) })).toContainText("1.000,00 €");
  });
});

test.describe("calendario", () => {
  const YEAR = "2031"; // un anno senza dati, ripulito a fine test
  test.beforeEach(async ({ page }) => { days.push(YEAR); await loginAs(page, ADMIN); });

  test("genera le festività, aggiunge una chiusura, la modifica e la elimina", async ({ page }) => {
    await page.goto(`/admin/calendario?anno=${YEAR}`);
    await expect(page.getByRole("heading", { name: `Nessun giorno nel ${YEAR}` })).toBeVisible();
    await page.getByRole("button", { name: `Genera le festività ${YEAR}` }).click();
    await expect(notice(page)).toContainText(new RegExp(`Aggiunte \\d+ festività per il ${YEAR}`));
    await expect(page.getByRole("row").filter({ hasText: "25/12/2031" })).toContainText("Festività");
    await expect(page.getByRole("row").filter({ hasText: "07/12/2031" })).toContainText(/Ambrogio/); // patrono di Milano
    await page.getByRole("button", { name: `Genera le festività ${YEAR}` }).click(); // di nuovo: non duplica
    await expect(notice(page)).toContainText(`Le festività ${YEAR} erano già tutte presenti`);
    await page.getByRole("button", { name: "+ Aggiungi un giorno" }).click();
    await dialog(page).getByLabel("Data").fill(`${YEAR}-12-24`);
    await dialog(page).getByLabel("Descrizione").fill("Vigilia di Natale");
    await dialog(page).getByRole("button", { name: "Aggiungi" }).click();
    const row = page.getByRole("row").filter({ hasText: "24/12/2031" });
    await expect(row).toContainText("Chiusura aziendale");
    await row.getByRole("button", { name: /Modifica/ }).click();
    await dialog(page).getByLabel("Descrizione").fill("Ponte di Natale");
    await dialog(page).getByRole("button", { name: "Salva" }).click();
    await expect(row).toContainText("Ponte di Natale");
    await row.getByRole("button", { name: /Elimina/ }).click();
    await dialog(page).getByRole("button", { name: "Elimina" }).click();
    await expect(page.getByRole("row").filter({ hasText: "24/12/2031" })).toHaveCount(0);
  });

  test("importa le chiusure da CSV (le date già presenti restano)", async ({ page }) => {
    await page.goto(`/admin/calendario?anno=${YEAR}`);
    await page.getByRole("button", { name: `Genera le festività ${YEAR}` }).click();
    await expect(notice(page)).toBeVisible();
    await page.getByRole("button", { name: "Importa chiusure da CSV" }).click();
    await dialog(page).getByLabel("File CSV").setInputFiles({ name: "chiusure.csv", mimeType: "text/csv", buffer: Buffer.from(`Data;Descrizione\n23/12/${YEAR};Ponte\n25/12/${YEAR};Natale doppione\n`) });
    await dialog(page).getByRole("button", { name: "Controlla il file" }).click();
    await expect(dialog(page).getByRole("status")).toContainText("1 nuovo");
    await dialog(page).getByRole("button", { name: "Importa" }).click();
    await expect(dialog(page)).toContainText("Importazione completata");
    await dialog(page).getByRole("button", { name: "Chiudi" }).click();
    await expect(page.getByRole("row").filter({ hasText: "23/12/2031" })).toContainText("Ponte");
    await expect(page.getByRole("row").filter({ hasText: "25/12/2031" })).toContainText("Festività"); // non sovrascritta
  });
});

test.describe("email", () => {
  test.beforeEach(async ({ page }) => loginAs(page, ADMIN));

  test("elenco, filtri e email di prova", async ({ page }) => {
    await page.goto("/admin/email");
    await page.getByRole("button", { name: "Invia un'email di prova a me" }).click();
    await expect(notice(page)).toContainText(`Email di prova inviata a ${ADMIN}`);
    const row = page.getByRole("row").filter({ hasText: "Email di prova" }).first();
    await expect(row).toContainText("Inviata");
    await expect(row).toContainText(ADMIN);
    await page.getByLabel("Stato", { exact: true }).selectOption({ label: "Fallita" });
    await expect(page.getByRole("heading", { name: "Nessuna email" })).toBeVisible();
    await page.getByLabel("Stato", { exact: true }).selectOption("");
    await page.getByLabel("Tipo", { exact: true }).selectOption({ label: "Email di prova" });
    await expect(page.getByRole("row").filter({ hasText: "CE approvato" })).toHaveCount(0);
  });

  test("«Invia subito» senza nulla in coda lo dice", async ({ page }) => {
    await page.goto("/admin/email");
    await page.getByRole("button", { name: "Invia subito quelle in coda" }).click();
    await expect(notice(page)).toContainText(/Nessuna email da inviare|Elaborate/);
  });
});

test.describe("CE eliminati", () => {
  test("si vede un CE eliminato e lo si ripristina", async ({ page }) => {
    const ce = await createCe(page, { phases: [{ name: "Delivery", lines: [{ activity: "X", profile: "Senior", hours: "8" }] }] });
    track(ce.id);
    await api(page, ADMIN, "DELETE", `/api/v1/ce/${ce.id}`);
    await loginAs(page, ADMIN);
    await page.goto("/admin/eliminati");
    const row = page.getByRole("row").filter({ hasText: ce.code });
    await expect(row).toBeVisible();
    await row.getByRole("button", { name: /Ripristina/ }).click();
    await dialog(page).getByRole("button", { name: "Ripristina" }).click();
    await expect(notice(page)).toContainText(`«${ce.code}» ripristinato`);
    await expect(page.getByRole("row").filter({ hasText: ce.code })).toHaveCount(0);
    await page.goto(`/ce?code=${ce.code}`);
    await expect(page.getByRole("link", { name: ce.code })).toBeVisible();
  });

  test("senza CE eliminati lo dice", async ({ page }) => {
    await loginAs(page, ADMIN);
    const all = await api(page, ADMIN, "GET", "/api/v1/ce?include_deleted=true&limit=200");
    test.skip((all.json.items as { deleted: boolean }[]).some((c) => c.deleted), "nel database ci sono CE eliminati");
    await page.goto("/admin/eliminati");
    await expect(page.getByRole("heading", { name: "Nessun CE eliminato" })).toBeVisible();
  });
});

test.describe("schermo piccolo", () => {
  test.skip(({ isMobile }) => !isMobile, "solo smartphone");
  test("le schede di amministrazione stanno nella larghezza dello schermo", async ({ page }) => {
    await loginAs(page, ADMIN);
    for (const path of ["utenti", "clienti", "collaboratori", "listino", "calendario", "email", "eliminati"]) {
      await page.goto(`/admin/${path}`);
      await expect(page.getByRole("heading", { name: "Amministrazione" })).toBeVisible();
      await page.waitForTimeout(400);
      await expectNoPageOverflow(page);
    }
  });
});
