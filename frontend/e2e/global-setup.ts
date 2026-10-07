/**
 * Prima dei test elimina i conti economici di prova (codice PS-E2E…) rimasti da esecuzioni interrotte,
 * così le prove dell'elenco trovano sempre i soliti dati di esempio.
 */
export default async function globalSetup() {
  const base = process.env.E2E_BASE_URL ?? "http://127.0.0.1:4173";
  const admin = process.env.E2E_ADMIN_EMAIL ?? "admin@huware.com";
  const login = await fetch(`${base}/api/v1/auth/dev-login`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ email: admin }) });
  if (!login.ok) throw new Error(`Accesso di sviluppo non riuscito per ${admin} (${login.status}): servono backend in locale, dati di esempio (make demo) e E2E_ADMIN_EMAIL se l'admin è un'altra email`);
  const headers = { Authorization: `Bearer ${(await login.json()).access_token}` };
  const list = await fetch(`${base}/api/v1/ce?code=PS-E2E&limit=200`, { headers });
  const items: { ce_id: string; code: string }[] = (await list.json()).items ?? [];
  for (const ce of items.filter((c) => c.code.startsWith("PS-E2E"))) await fetch(`${base}/api/v1/ce/${ce.ce_id}`, { method: "DELETE", headers });
  if (items.length) console.log(`Ripulito: eliminati ${items.length} CE di prova rimasti da esecuzioni precedenti`);
}
