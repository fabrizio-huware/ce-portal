/** Integrazioni: programmi esterni che agiscono con un account di servizio Google. */

export const PERMISSIONS = [
  { key: "create", label: "Creare CE", short: "Creare" },
  { key: "edit", label: "Modificare le proprie bozze", short: "Modificare" },
  { key: "read", label: "Leggere elenchi e riepiloghi", short: "Leggere" },
  { key: "export", label: "Esportare il riepilogo in PDF", short: "PDF" },
] as const;

export type PermissionKey = (typeof PERMISSIONS)[number]["key"];

const ORDER: string[] = PERMISSIONS.map((p) => p.key);

/** Come il server: minuscolo, finisce con .iam.gserviceaccount.com. */
const SERVICE_ACCOUNT = /^[a-z0-9][a-z0-9._-]*@[a-z0-9.-]+\.iam\.gserviceaccount\.com$/;

export const isServiceAccountEmail = (value: string): boolean => {
  const v = value.trim().toLowerCase();
  return v.length <= 320 && SERVICE_ACCOUNT.test(v);
};

/** Aggiunge o toglie un permesso mantenendo l'ordine canonico e senza doppioni. */
export function togglePermission(current: string[], key: PermissionKey, on: boolean): PermissionKey[] {
  const set = new Set(current);
  if (on) set.add(key);
  else set.delete(key);
  return ORDER.filter((k) => set.has(k)) as PermissionKey[];
}

/** Etichette brevi dei permessi, nell'ordine canonico; i permessi sconosciuti si ignorano. */
export function permissionLabels(granted: string[]): string[] {
  return PERMISSIONS.filter((p) => granted.includes(p.key)).map((p) => p.short);
}

/** L'indirizzo che il programma esterno deve usare come audience: l'indirizzo del portale, senza «/» finale. */
export const portalAudience = (origin: string): string => origin.trim().replace(/\/+$/, "");

type Person = { id: string; full_name: string; role: string; is_active: boolean };

/** A chi si può assegnare un CE creato da un'integrazione: presale attivi, in ordine alfabetico. */
export function presaleChoices<T extends Person>(users: T[]): T[] {
  return users
    .filter((u) => u.role === "presale" && u.is_active)
    .sort((a, b) => a.full_name.localeCompare(b.full_name, "it", { sensitivity: "base" }));
}
