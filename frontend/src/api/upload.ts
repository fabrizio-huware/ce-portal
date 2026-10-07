import type { components } from "./schema";
import { API_BASE } from "./client";
import { authStore } from "./authStore";
import { ApiError } from "../lib/errors";

export type ImportResult = components["schemas"]["ImportResult"];

/**
 * Invia un file CSV a un endpoint di importazione.
 * Con `dryRun` il server non scrive nulla e restituisce solo l'anteprima (conteggi ed errori per riga).
 * Un errore di riga restituisce comunque il risultato (con `errors`): è l'utente a decidere cosa fare.
 */
export async function uploadCsv(path: string, file: File, dryRun: boolean): Promise<ImportResult> {
  const form = new FormData();
  form.append("file", file);
  const token = authStore.getToken();
  const response = await fetch(`${API_BASE}${path}?dry_run=${dryRun}`, { method: "POST", headers: token ? { Authorization: `Bearer ${token}` } : {}, body: form });
  if (response.status === 401) authStore.expire();
  const body = await response.json().catch(() => null);
  if (response.ok || (response.status === 422 && body && typeof body === "object" && "errors" in body)) return body as ImportResult;
  throw new ApiError(response.status, body);
}
