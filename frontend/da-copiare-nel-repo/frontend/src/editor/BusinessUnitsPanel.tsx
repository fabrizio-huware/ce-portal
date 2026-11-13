import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { api, unwrap } from "../api/client";
import { useBusinessUnits } from "../api/lookups";
import type { components } from "../api/schema";
import { Problems } from "../components/ActionsBar";
import { BusinessUnitPicker } from "../components/BusinessUnitPicker";
import { Button } from "../components/ui/Button";
import { errorDetails } from "../lib/errors";
import { choosableForCe, undeclaredUnits } from "../lib/businessUnits";
import type { Draft } from "./model";

type Detail = components["schemas"]["CEDetail"];
type Employee = components["schemas"]["EmployeeOut"];

/** Business unit coinvolte: valgono per tutto il CE e si salvano subito (non fanno parte del contenuto da salvare). */
export function BusinessUnitsPanel({ detail, draft, employees }: { detail: Detail; draft: Draft; employees: Employee[] }) {
  const units = useBusinessUnits();
  const qc = useQueryClient();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<{ message: string; issues: string[] } | null>(null);
  const declared = detail.business_units.map((u) => u.id);
  // le righe non ancora salvate contano subito: l'avviso non aspetta il salvataggio
  const employeeIds = draft.phases.flatMap((p) => p.lines.map((l) => l.employeeId).filter(Boolean));
  const missing = undeclaredUnits(employeeIds, employees, declared);
  async function save(ids: string[]) {
    setBusy(true); setError(null);
    try {
      unwrap(await api.PUT("/api/v1/ce/{ce_id}/business-units", { params: { path: { ce_id: detail.ce.id } }, body: { business_unit_ids: ids } }));
      await qc.invalidateQueries({ queryKey: ["ce-edit", detail.ce.id] });
      for (const k of ["ce", "ce-list", "ce-history"]) void qc.invalidateQueries({ queryKey: [k] });
    } catch (err) { setError(errorDetails(err)); } finally { setBusy(false); }
  }
  const canEdit = detail.actions.set_business_units && !busy;
  return (
    <section className="card space-y-3 p-4 sm:p-5" aria-label="Business unit coinvolte">
      <Problems error={error} />
      <BusinessUnitPicker units={choosableForCe(units.data ?? [], declared)} value={declared} disabled={!canEdit} required
        onChange={(ids) => { if (ids.length > 0) void save(ids); }}
        hint={declared.length === 0 ? "Questo CE non ha business unit: indicane almeno una per poterlo inviare in approvazione." : "Valgono per tutto il CE e decidono chi lo vede. Si cambiano finché è bozza o rifiutato, e ogni cambio è registrato."} />
      {missing.length > 0 && (
        <div role="alert" className="rounded-xl border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-900">
          <p className="font-medium">Nelle righe ci sono collaboratori di business unit che non sono coinvolte: finché non coincidono non si può inviare il CE in approvazione.</p>
          <ul className="mt-2 space-y-1">
            {missing.map((u) => (
              <li key={u.id} className="flex flex-wrap items-center gap-2">
                <span><strong>{u.name}</strong></span>
                {detail.actions.set_business_units && <Button size="sm" variant="secondary" disabled={busy} onClick={() => void save([...declared, u.id])}>Aggiungi {u.name}<span className="sr-only"> alle business unit coinvolte</span></Button>}
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}
