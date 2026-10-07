import { expect, test } from "@playwright/test";

import { ADMIN, PRESALE, expectNoPageOverflow, loginAs } from "./helpers";

test("senza accesso si viene portati alla pagina di login", async ({ page }) => {
  await page.goto("/ce");
  await expect(page).toHaveURL(/\/login$/);
  await expect(page.getByRole("heading", { name: "Accedi" })).toBeVisible();
  await expect(page.getByRole("img", { name: "Huware" }).first()).toBeVisible();
  await expectNoPageOverflow(page);
});

test("un utente non registrato riceve un messaggio chiaro", async ({ page }) => {
  await page.goto("/login");
  await page.getByLabel("Email di un utente registrato").fill("sconosciuto@huware.com");
  await page.getByRole("button", { name: "Entra senza Google" }).click();
  await expect(page.getByRole("alert")).toContainText("non abilitato");
  await expect(page).toHaveURL(/\/login$/);
});

test("accesso, persistenza dopo il ricaricamento e uscita", async ({ page }) => {
  await loginAs(page, ADMIN);
  await expect(page.getByRole("heading", { name: "Conti economici", level: 1 })).toBeVisible();
  await page.reload();
  await expect(page).toHaveURL(/\/ce$/);
  await expect(page.getByRole("heading", { name: "Conti economici", level: 1 })).toBeVisible();
  const mobile = (page.viewportSize()?.width ?? 1280) < 768;
  if (mobile) await page.getByRole("button", { name: "Menu" }).click();
  await page.getByRole("button", { name: "Esci" }).click();
  await expect(page).toHaveURL(/\/login$/);
  await page.goto("/ce");
  await expect(page).toHaveURL(/\/login$/); // il token è stato cancellato
});

test("la sessione scaduta riporta al login con un avviso", async ({ page }) => {
  await loginAs(page, PRESALE);
  await page.evaluate(() => sessionStorage.setItem("ce.token", "token-non-valido"));
  await page.reload();
  await expect(page).toHaveURL(/\/login$/);
  await expect(page.getByText("La sessione è scaduta")).toBeVisible();
});

test("dopo il login si torna alla pagina richiesta", async ({ page }) => {
  await page.goto("/ce?status=approved");
  await expect(page).toHaveURL(/\/login$/);
  await page.getByLabel("Email di un utente registrato").fill(ADMIN);
  await page.getByRole("button", { name: "Entra senza Google" }).click();
  await expect(page).toHaveURL(/\/ce\?status=approved$/);
});
