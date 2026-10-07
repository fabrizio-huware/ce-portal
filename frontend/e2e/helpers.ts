import { expect, type Page } from "@playwright/test";

export const ADMIN = process.env.E2E_ADMIN_EMAIL ?? "admin@huware.com"; // l'admin iniziale del backend
export const PRESALE = "anna.presale@huware.com";
export const VIEWER = "vera.viewer@huware.com";

/** Accesso con il login simulato del backend locale. */
export async function loginAs(page: Page, email: string) {
  await page.goto("/login");
  await page.getByLabel("Email di un utente registrato").fill(email);
  await page.getByRole("button", { name: "Entra senza Google" }).click();
  await expect(page).toHaveURL(/\/ce$/);
}

export async function isMobile(page: Page) {
  return (page.viewportSize()?.width ?? 1280) < 768;
}

/** Nessuna barra di scorrimento orizzontale sulla pagina. */
export async function expectNoPageOverflow(page: Page) {
  // Si confronta con la larghezza nominale dello schermo: su mobile il browser, davanti a una pagina troppo larga,
  // allarga la finestra e `innerWidth` cresce con lei, nascondendo il problema.
  const width = page.viewportSize()!.width;
  const scrollWidth = await page.evaluate(() => document.documentElement.scrollWidth);
  expect(scrollWidth, "la pagina non deve scorrere in orizzontale").toBeLessThanOrEqual(width + 1);
}

/** Chiamata diretta alle API con il token di un utente (per preparare o verificare dati). */
export async function apiGet(page: Page, email: string, path: string) {
  const login = await page.request.post("/api/v1/auth/dev-login", { data: { email } });
  const token = (await login.json()).access_token;
  const response = await page.request.get(path, { headers: { Authorization: `Bearer ${token}` } });
  return { status: response.status(), json: await response.json() };
}

/** Su schermi stretti i filtri stanno dietro al pulsante "Filtri". */
export async function openFilters(page: Page) {
  await page.getByRole("region", { name: "Filtri" }).waitFor(); // la pagina deve essere già disegnata
  const button = page.getByRole("button", { name: /^Filtri/ });
  if (await button.isVisible()) {
    if ((await button.getAttribute("aria-expanded")) !== "true") await button.click();
  }
}

export function count(page: Page) {
  return page.locator('[aria-live="polite"]');
}

// ---------------------------------------------------------------- CE di prova creati via API (e rimossi alla fine di ogni test)
const created: string[] = [];
export const uniqueCode = (prefix = "PS-E2E") => `${prefix}-${Date.now().toString(36).toUpperCase()}${Math.floor(Math.random() * 90 + 10)}`;

export async function api(page: Page, email: string, method: "GET" | "POST" | "PUT" | "PATCH" | "DELETE", path: string, data?: unknown) {
  const login = await page.request.post("/api/v1/auth/dev-login", { data: { email } });
  const token = (await login.json()).access_token;
  const response = await page.request.fetch(path, { method, headers: { Authorization: `Bearer ${token}` }, data: data as never });
  const text = await response.text();
  return { status: response.status(), json: text ? JSON.parse(text) : null };
}

export type SeedLine = { activity: string; profile: string; hours?: string; alloc?: Record<string, string>; employee?: string };
export type SeedPhase = { name: string; contingency?: string; lines: SeedLine[] };

export async function createCe(page: Page, opts: { code?: string; mode?: "hours" | "percent"; start?: string; end?: string; phases?: SeedPhase[]; by?: string }) {
  const by = opts.by ?? PRESALE;
  const code = opts.code ?? uniqueCode();
  const [start, end] = [opts.start ?? "2026-03-02", opts.end ?? "2026-05-29"];
  const clients = await api(page, by, "GET", "/api/v1/clients/lookup?q=Alfa");
  const clientId = clients.json[0].id;
  const created1 = await api(page, by, "POST", "/api/v1/ce", { code, client_id: clientId, project_name: `Progetto ${code}`, start_date: start, end_date: end, planning_mode: opts.mode ?? "hours", standard_phases: false });
  expect(created1.status, JSON.stringify(created1.json)).toBe(201);
  const id: string = created1.json.ce.id;
  created.push(id);
  const saved = await putContent(page, { id, code, clientId, start, end, mode: opts.mode ?? "hours", phases: opts.phases ?? [{ name: "Delivery", lines: [] }], revision: created1.json.version.revision, by });
  return { id, code, clientId, revision: saved.json.version.revision as number, start, end, mode: opts.mode ?? "hours", phases: opts.phases ?? [], by };
}

export async function putContent(page: Page, c: { id: string; code: string; clientId: string; start: string; end: string; mode: string; phases: SeedPhase[]; revision: number; by: string }) {
  const profiles = (await api(page, c.by, "GET", "/api/v1/profiles")).json as { id: string; name: string }[];
  const employees = ((await api(page, c.by, "GET", "/api/v1/employees?limit=200")).json.items ?? []) as { id: string; first_name: string; last_name: string }[];
  const pid = (name: string) => profiles.find((p) => p.name === name)!.id;
  const eid = (name?: string) => (name ? employees.find((e) => `${e.last_name} ${e.first_name}` === name)?.id ?? null : null);
  const res = await api(page, c.by, "PUT", `/api/v1/ce/${c.id}/content`, {
    expected_revision: c.revision,
    header: { client_id: c.clientId, project_name: `Progetto ${c.code}`, start_date: c.start, end_date: c.end, planning_mode: c.mode },
    phases: c.phases.map((p) => ({
      name: p.name, contingency_pct: p.contingency ?? "0",
      lines: p.lines.map((l) => ({
        activity: l.activity, profile_id: pid(l.profile), employee_id: eid(l.employee), hours: c.mode === "hours" ? (l.hours ?? "0") : null,
        allocations: c.mode === "percent" ? Object.entries(l.alloc ?? {}).map(([month, pct]) => ({ month, pct })) : [],
      })),
    })),
  });
  expect(res.status, JSON.stringify(res.json)).toBe(200);
  return res;
}

/** Registra un CE creato dall'interfaccia, così viene eliminato a fine test. */
export const track = (id: string) => created.push(id);

/** Da chiamare in afterEach: elimina (logicamente) i CE creati dal test, così gli altri test trovano i soliti dati. */
export async function cleanup(page: Page) {
  while (created.length) {
    const id = created.pop()!;
    await api(page, ADMIN, "DELETE", `/api/v1/ce/${id}`).catch(() => {});
  }
}
