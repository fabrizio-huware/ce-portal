export type CeStatus = "draft" | "submitted" | "approved" | "rejected";

export const STATUS: Record<CeStatus, { label: string; classes: string; dot: string }> = {
  draft: { label: "Bozza", classes: "bg-surface text-muted border-line", dot: "bg-muted" },
  submitted: { label: "In approvazione", classes: "bg-amber-50 text-amber-800 border-amber-200", dot: "bg-amber-500" },
  approved: { label: "Approvato", classes: "bg-emerald-50 text-emerald-800 border-emerald-200", dot: "bg-emerald-500" },
  rejected: { label: "Rifiutato", classes: "bg-red-50 text-red-800 border-red-200", dot: "bg-red-500" },
};

export const ROLE_LABEL: Record<string, string> = { admin: "Amministratore", presale: "Presale", bu_manager: "Responsabile di business unit", viewer: "Viewer" };
export const MODE_LABEL: Record<string, string> = { hours: "Ore", percent: "Percentuali" };

export const HISTORY_LABEL: Record<string, string> = {
  create: "Creato", save: "Salvato", submit: "Inviato in approvazione", withdraw: "Ritirato", approve: "Approvato",
  reject: "Rifiutato", new_version: "Nuova versione", discard_version: "Versione scartata", realign: "Riallineato",
  duplicate: "Duplicato", delete: "Eliminato", restore: "Ripristinato", export: "Esportato",
  assign: "Assegnato a un presale", create_by_integration: "Creato da un'integrazione",
};

/** Dettaglio breve di alcune azioni della cronologia (a chi è stato assegnato, quale riferimento esterno). */
export function historyDetail(action: string, changes: unknown): string | null {
  const c = changes && typeof changes === "object" ? (changes as Record<string, unknown>) : {};
  const text = (k: string) => (typeof c[k] === "string" && c[k] !== "" ? (c[k] as string) : null);
  if (action === "assign") return text("to") ? `a ${text("to")}` : null;
  if (action === "create_by_integration") return text("external_ref") ? `rif. ${text("external_ref")}` : null;
  return null;
}
