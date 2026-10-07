/** Messaggio leggibile a partire da un errore dell'API (FastAPI) o di rete. */
export function errorMessage(error: unknown): string {
  if (error instanceof Error) return error.message;
  if (typeof error === "string") return error;
  if (error && typeof error === "object") {
    const detail = (error as { detail?: unknown }).detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {
      return detail.map((d) => (d && typeof d === "object" && "msg" in d ? String((d as { msg: unknown }).msg) : String(d))).join("; ");
    }
    if (detail && typeof detail === "object") {
      const d = detail as { message?: string; issues?: string[] };
      return [d.message, ...(d.issues && d.issues[0] !== d.message ? d.issues : [])].filter(Boolean).join(": ");
    }
  }
  return "Si è verificato un errore imprevisto";
}

export class ApiError extends Error {
  constructor(public status: number, public body: unknown) {
    super(errorMessage(body));
  }
}

/** Messaggio principale e, se l'API le fornisce, l'elenco completo dei problemi (errori 422). */
export function errorDetails(error: unknown): { message: string; issues: string[]; status?: number; body?: unknown } {
  const body = error instanceof ApiError ? error.body : error;
  const status = error instanceof ApiError ? error.status : undefined;
  const detail = body && typeof body === "object" ? (body as { detail?: unknown }).detail : undefined;
  if (detail && typeof detail === "object" && !Array.isArray(detail)) {
    const d = detail as { message?: string; issues?: string[] };
    return { message: d.message ?? errorMessage(error), issues: d.issues ?? [], status, body };
  }
  return { message: errorMessage(error), issues: [], status, body };
}
