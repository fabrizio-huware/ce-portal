import { toggleUnit } from "../lib/businessUnits";

type Unit = { id: string; name: string; is_active: boolean };

/** Scelta multipla delle business unit coinvolte in un CE (caselle a forma di etichetta, accessibili da tastiera). */
export function BusinessUnitPicker({ units, value, onChange, disabled, required, invalid, hint }: {
  units: Unit[]; value: string[]; onChange: (ids: string[]) => void; disabled?: boolean; required?: boolean; invalid?: boolean; hint?: string;
}) {
  return (
    <fieldset disabled={disabled} className="min-w-0 border-0 p-0">
      <legend className="label">Business unit coinvolte{required ? " (almeno una)" : ""}</legend>
      <div className="flex flex-wrap gap-2">
        {units.length === 0 && <p className="text-sm text-muted">Nessuna business unit disponibile: la crea un amministratore.</p>}
        {units.map((u) => {
          const on = value.includes(u.id);
          return (
            <label key={u.id} className={`inline-flex cursor-pointer items-center gap-2 rounded-full border px-3 py-1.5 text-sm focus-within:ring-2 focus-within:ring-teal-600 ${on ? "border-ink bg-ink text-white" : invalid && value.length === 0 ? "border-red-600 bg-paper" : "border-line bg-paper"} ${disabled ? "cursor-not-allowed opacity-60" : ""}`}>
              <input type="checkbox" className="sr-only" checked={on} onChange={(e) => onChange(toggleUnit(value, u.id, e.target.checked))} />
              <span>{u.name}{u.is_active ? "" : " (disattivata)"}</span>
            </label>
          );
        })}
      </div>
      {hint && <p className="mt-1 text-xs text-muted">{hint}</p>}
    </fieldset>
  );
}
