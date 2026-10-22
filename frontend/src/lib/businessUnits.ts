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
