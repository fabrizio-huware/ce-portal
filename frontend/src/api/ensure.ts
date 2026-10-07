import { ApiError } from "../lib/errors";

/** Per le risposte senza corpo (204): solleva un errore leggibile se la chiamata non è riuscita. */
export function ensureOk(result: { error?: unknown; response: Response }): void {
  if (result.error !== undefined || !result.response.ok) throw new ApiError(result.response.status, result.error);
}
