import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

import { PRESALE, VIEWER, loginAs } from "./helpers";

async function audit(page: Page, label: string) {
  const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).analyze();
  const summary = results.violations.map((v) => `${v.id} (${v.impact}): ${v.nodes.slice(0, 3).map((n) => n.target.join(" ")).join(" | ")}`);
  expect(summary, `violazioni di accessibilità in "${label}"`).toEqual([]);
}

test("login", async ({ page }) => {
  await page.goto("/login");
  await expect(page.getByRole("heading", { name: "Accedi" })).toBeVisible();
  await audit(page, "login");
});

test("elenco e dettaglio (admin/presale)", async ({ page }) => {
  await loginAs(page, PRESALE);
  await expect(page.getByRole("link", { name: "PS-ALFA-ECOM-PJT" }).first()).toBeVisible();
  await audit(page, "elenco");
  await page.getByRole("link", { name: /PS-ALFA-ECOM-PJT/ }).first().click();
  await expect(page.getByRole("heading", { name: "PS-ALFA-ECOM-PJT", level: 1 })).toBeVisible();
  await audit(page, "dettaglio");
  for (const name of ["Riepilogo", "Staffing mensile", "Versioni", "Storico"]) {
    await page.getByRole("tab", { name }).click();
    await audit(page, `scheda ${name}`);
  }
});

test("elenco e dettaglio (viewer)", async ({ page }) => {
  await loginAs(page, VIEWER);
  await expect(page.getByRole("link", { name: "PS-ALFA-ECOM-PJT" }).first()).toBeVisible();
  await audit(page, "elenco viewer");
  await page.getByRole("link", { name: /PS-ALFA-ECOM-PJT/ }).first().click();
  await expect(page.getByText("Totale generale")).toBeVisible();
  await audit(page, "dettaglio viewer");
});

test("editor (a ore e a percentuali) e nuovo CE", async ({ page }) => {
  const { cleanup, createCe } = await import("./helpers");
  try {
    const hours = await createCe(page, { phases: [{ name: "Delivery", lines: [{ activity: "Sviluppo", profile: "Senior", hours: "16" }] }] });
    const percent = await createCe(page, { mode: "percent", phases: [{ name: "Allocazione", lines: [{ activity: "Sviluppo", profile: "Senior", alloc: { "2026-03-01": "50" } }] }] });
    await loginAs(page, PRESALE);
    await page.goto(`/ce/${hours.id}/modifica`);
    await expect(page.getByRole("heading", { name: "Fasi e righe" })).toBeVisible();
    await audit(page, "editor a ore");
    await page.goto(`/ce/${percent.id}/modifica`);
    await expect(page.getByRole("heading", { name: "Fasi e righe" })).toBeVisible();
    await audit(page, "editor a percentuali");
    await page.goto("/ce/nuovo");
    await audit(page, "nuovo CE");
    await page.goto(`/ce/${hours.id}`);
    await expect(page.getByRole("button", { name: "Altre azioni" })).toBeVisible();
    await audit(page, "dettaglio con azioni");
  } finally {
    await cleanup(page);
  }
});
