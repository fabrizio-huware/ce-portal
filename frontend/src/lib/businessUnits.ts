/** Business unit: stanno sopra le practice (business unit → practice → collaboratori) e decidono chi vede un CE. */

/** Business unit di sistema: accoglie le practice non ancora assegnate. Non si rinomina né si disattiva. */
export const SYSTEM_BUSINESS_UNIT = "Da assegnare";

export const isSystemBusinessUnit = (name: string): boolean => name.trim().toLowerCase() === SYSTEM_BUSINESS_UNIT.toLowerCase();

type Unit = { id: string; name: string; is_active: boolean };

/**
 * Business unit che si possono scegliere: quelle attive e quella già assegnata (anche se disattivata, altrimenti il
 * modulo non potrebbe mostrarla). Alle persone non si assegna «Da assegnare»: serve solo per le practice.
 */
export function choosableBusinessUnits<T extends Unit>(units: T[], currentId: string, forPeople: boolean): T[] {
  return units.filter((u) => u.id === currentId || (u.is_active && !(forPeople && isSystemBusinessUnit(u.name))));
}

/** Solo presale e responsabili di business unit hanno una business unit. */
export const canHaveBusinessUnit = (role: string): boolean => role === "presale" || role === "bu_manager";

/** Il responsabile deve averla; per il presale è facoltativa (serve a migrare i dati esistenti). */
export const roleNeedsBusinessUnit = (role: string): boolean => role === "bu_manager";

/** Aggiunge o toglie una business unit mantenendo l'ordine di scelta e senza doppioni. */
export function toggleUnit(ids: string[], id: string, on: boolean): string[] {
  const rest = ids.filter((x) => x !== id);
  return on ? [...rest, id] : rest;
}

/**
 * Business unit che si possono coinvolgere in un CE: quelle attive e vere (non «Da assegnare»), più quelle già
 * coinvolte anche se nel frattempo disattivate, altrimenti non si potrebbero più mostrare né togliere.
 */
export function choosableForCe<T extends Unit>(units: T[], selectedIds: string[]): T[] {
  return units.filter((u) => selectedIds.includes(u.id) || (u.is_active && !isSystemBusinessUnit(u.name)));
}

type EmployeeUnit = { id: string; business_unit_id: string; business_unit_name: string };

/**
 * Business unit dei collaboratori indicati nelle righe che non sono tra quelle coinvolte, in ordine alfabetico.
 * Quella di sistema «Da assegnare» non conta: una practice non ancora assegnata non crea incoerenze.
 */
export function undeclaredUnits(employeeIds: string[], employees: EmployeeUnit[], declaredIds: string[]): { id: string; name: string }[] {
  const wanted = new Set(employeeIds);
  const found = new Map<string, string>();
  for (const e of employees) {
    if (!wanted.has(e.id) || isSystemBusinessUnit(e.business_unit_name) || declaredIds.includes(e.business_unit_id)) continue;
    found.set(e.business_unit_id, e.business_unit_name);
  }
  return [...found].map(([id, name]) => ({ id, name })).sort((a, b) => a.name.localeCompare(b.name, "it", { sensitivity: "base" }));
}

type VisibilityReport = {
  ces_without_business_units: number;
  people_without_business_unit: string[];
  practices_unassigned: number;
};

const plural = (n: number, one: string, many: string) => `${n} ${n === 1 ? one : many}`;

/**
 * Che cosa cambierebbe in modo sgradito accendendo la visibilità per business unit, in italiano, pronto da
 * mostrare prima di confermare. Vuota se non manca nulla.
 */
export function visibilityWarnings(report: VisibilityReport): string[] {
  const out: string[] = [];
  if (report.ces_without_business_units > 0) {
    const n = report.ces_without_business_units;
    out.push(`${plural(n, "CE non ha", "CE non hanno")} business unit: ${n === 1 ? "lo vedranno" : "li vedranno"} solo l'autore e gli amministratori finché non assegni le business unit.`);
  }
  const people = report.people_without_business_unit;
  if (people.length > 0) {
    const shown = people.slice(0, 5).join(", ") + (people.length > 5 ? ` e altri ${people.length - 5}` : "");
    out.push(`${plural(people.length, "presale non ha", "presale non hanno")} business unit e ${people.length === 1 ? "vedrà" : "vedranno"} solo i propri CE: ${shown}.`);
  }
  if (report.practices_unassigned > 0) {
    out.push(`${plural(report.practices_unassigned, "practice è", "practice sono")} ancora in «${SYSTEM_BUSINESS_UNIT}»: i suoi collaboratori non appartengono a nessuna business unit.`);
  }
  return out;
}
