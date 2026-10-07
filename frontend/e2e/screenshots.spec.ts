import { test } from "@playwright/test";
import { mkdirSync } from "node:fs";

import { ADMIN, PRESALE, VIEWER, loginAs } from "./helpers";

// Raccolta di schermate per la revisione grafica: si esegue solo con  E2E_SCREENSHOTS=1
test.skip(!process.env.E2E_SCREENSHOTS, "solo su richiesta");
const DIR = "e2e/screens";
mkdirSync(DIR, { recursive: true });

test("schermate", async ({ page }, info) => {
  const shot = (name: string, fullPage = false) => page.screenshot({ path: `${DIR}/${info.project.name}-${name}.png`, fullPage });
  await page.goto("/login");
  await page.getByRole("heading", { name: "Accedi" }).waitFor();
  await shot("01-login");

  await loginAs(page, PRESALE);
  await page.getByRole("link", { name: "PS-ALFA-ECOM-PJT" }).first().waitFor();
  await shot("02-elenco");
  if (info.project.name === "mobile") {
    await page.getByRole("button", { name: /^Filtri/ }).click();
    await shot("03-elenco-filtri");
    await page.getByRole("button", { name: "Menu" }).click();
    await shot("04-menu");
  }
  await page.goto("/ce");
  await page.getByRole("link", { name: /PS-ALFA-ECOM-PJT/ }).first().click();
  await page.getByRole("heading", { name: "PS-ALFA-ECOM-PJT", level: 1 }).waitFor();
  await shot("05-dettaglio");
  await shot("06-dettaglio-intero", true);
  await page.getByRole("tab", { name: "Staffing mensile" }).click();
  await shot("07-staffing");
  await page.getByRole("tab", { name: "Riepilogo" }).click();
  await shot("08-riepilogo");

  // editor (admin/presale)
  await page.goto("/ce?code=BETA-MIG");
  await page.getByRole("link", { name: /PS-BETA-MIG-PJT/ }).first().click();
  await page.getByRole("link", { name: "Modifica" }).click();
  await page.getByRole("heading", { name: "Fasi e righe" }).waitFor();
  await page.waitForTimeout(900);
  await shot("11-editor", true);
  await page.goto("/ce?code=DELTA-APP");
  await page.getByRole("link", { name: /PS-DELTA-APP-PJT/ }).first().click();
  await page.getByRole("link", { name: "Modifica" }).click();
  await page.getByRole("heading", { name: "Fasi e righe" }).waitFor();
  await page.waitForTimeout(900);
  await shot("12-editor-percentuali", true);
  await page.goto("/ce/nuovo");
  await shot("13-nuovo-ce", true);
  await page.goto("/dashboard/portfolio");
  await page.getByText("Ricavi per mese").first().waitFor();
  await page.waitForTimeout(600);
  await shot("14-dashboard-portfolio", true);
  await page.goto("/dashboard/risorse?from=2026-01&to=2026-12&pipeline=1");
  await page.getByRole("heading", { name: "Impegno dei collaboratori" }).waitFor();
  await page.waitForTimeout(600);
  await shot("15-dashboard-risorse", true);

  await page.evaluate(() => sessionStorage.clear());
  await loginAs(page, ADMIN);
  for (const [name, path, wait] of [["16-admin-utenti", "/admin/utenti", "Anna Presale"], ["17-admin-listino", "/admin/listino?anno=2026", "Specialist"], ["18-admin-calendario", "/admin/calendario?anno=2026", "Natale"], ["19-admin-email", "/admin/email", "Oggetto"]] as const) {
    await page.goto(path);
    await page.getByText(wait).first().waitFor();
    await page.waitForTimeout(300);
    await shot(name, true);
  }
  await page.goto("/admin/collaboratori");
  await page.getByRole("button", { name: "Importa da CSV" }).click();
  await page.getByLabel("File CSV").setInputFiles({ name: "collaboratori.csv", mimeType: "text/csv", buffer: Buffer.from("Nome;Cognome;Profilo;Attivo\nMario;Rossi;Senior;sì\nAnna;Bianchi;Inesistente;sì\n;Verdi;Senior;sì\n") });
  await page.getByRole("button", { name: "Controlla il file" }).click();
  await page.getByRole("alert").waitFor();
  await shot("20-admin-import-errori");
  await page.evaluate(() => sessionStorage.clear());
  await loginAs(page, VIEWER);
  await page.getByRole("link", { name: "PS-ALFA-ECOM-PJT" }).first().waitFor();
  await shot("09-viewer-elenco");
  await page.getByRole("link", { name: /PS-ALFA-ECOM-PJT/ }).first().click();
  await page.getByText("Totale generale").waitFor();
  await shot("10-viewer-dettaglio", true);
});
