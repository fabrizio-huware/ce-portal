export type ProfileOption = { id: string; name: string; rates: { year: number }[] };
export type EmployeeOption = { id: string; first_name: string; last_name: string; default_profile_id: string };

/** `unavailable` = nota da mostrare sulla riga quando il profilo di default del collaboratore non si può usare. */
export type ProfileForEmployee = { profileId: string; unavailable: string | null };

/**
 * Il profilo di una riga quando si sceglie il collaboratore.
 *
 * Regola (richiesta dall'utente): il profilo **segue sempre** il collaboratore scelto, anche se la riga ne aveva un altro
 * scelto a mano; poi resta modificabile. Togliendo il collaboratore il profilo non cambia.
 * Se il profilo di default non si può usare (nessuna tariffa per l'anno del CE, oppure profilo disattivato) la riga
 * conserva il profilo che aveva e si restituisce la nota da mostrare, invece di lasciare un profilo non selezionabile.
 */
export function profileForEmployee(currentProfileId: string, employee: EmployeeOption | undefined, profiles: ProfileOption[], rateYear: number): ProfileForEmployee {
  if (!employee) return { profileId: currentProfileId, unavailable: null };
  const target = profiles.find((p) => p.id === employee.default_profile_id);
  if (target && target.rates.some((r) => r.year === rateYear)) return { profileId: target.id, unavailable: null };
  const who = `${employee.last_name} ${employee.first_name}`;
  return {
    profileId: currentProfileId,
    unavailable: target
      ? `Il profilo di default di ${who} (${target.name}) non ha la tariffa ${rateYear}: scegli il profilo.`
      : `Il profilo di default di ${who} non è disponibile: scegli il profilo.`,
  };
}
