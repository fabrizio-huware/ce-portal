import { ClientSelect } from "../components/ClientSelect";
import type { Draft } from "./model";
import { monthsBetween, setHeader } from "./model";
import * as m from "./model";
import { numberError } from "./numbers";
import { month as monthLabel } from "../lib/format";
import type { Calculation } from "../api/types";

type Props = { draft: Draft; update: (fn: (d: Draft) => Draft) => void; invalid: Set<string>; calc: Calculation | undefined };

export function GeneralForm({ draft: d, update, invalid, calc }: Props) {
  const set = (patch: Partial<Draft>) => update((x) => setHeader(x, patch));
  const bad = (id: string) => (invalid.has(id) ? "border-red-600" : "");
  const months = monthsBetween(d.startDate, d.endDate);
  return (
    <div className="space-y-6">
      <section className="card p-4 sm:p-5" aria-label="Dati generali">
        <h2 className="mb-4 text-lg font-medium tracking-normal">Dati generali</h2>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <div><label htmlFor="g-client" className="label">Cliente</label><ClientSelect id="g-client" value={d.clientId} onChange={(clientId) => set({ clientId })} invalid={invalid.has("clientId")} /></div>
          <div className="lg:col-span-2"><label htmlFor="g-project" className="label">Nome del progetto</label><input id="g-project" className={`field ${bad("projectName")}`} value={d.projectName} onChange={(e) => set({ projectName: e.target.value })} maxLength={300} /></div>
          <div><label htmlFor="g-start" className="label">Inizio</label><input id="g-start" type="date" className={`field ${bad("period")}`} value={d.startDate} onChange={(e) => set({ startDate: e.target.value })} /></div>
          <div><label htmlFor="g-end" className="label">Fine</label><input id="g-end" type="date" className={`field ${bad("period")}`} value={d.endDate} onChange={(e) => set({ endDate: e.target.value })} /></div>
          <fieldset><legend className="label">Pianificazione</legend>
            <div className="flex gap-4 pt-2 text-sm">
              <label className="flex items-center gap-2"><input type="radio" name="mode" className="accent-ink" checked={d.mode === "hours"} onChange={() => set({ mode: "hours" })} /> A ore</label>
              <label className="flex items-center gap-2"><input type="radio" name="mode" className="accent-ink" checked={d.mode === "percent"} onChange={() => set({ mode: "percent" })} /> A percentuali mensili</label>
            </div>
          </fieldset>
          <div><label htmlFor="g-bu" className="label">Business unit</label><input id="g-bu" className="field" value={d.businessUnit} onChange={(e) => set({ businessUnit: e.target.value })} maxLength={100} /></div>
          <div><label htmlFor="g-sf" className="label">Opportunità Salesforce</label><input id="g-sf" className="field" value={d.salesforce} onChange={(e) => set({ salesforce: e.target.value })} maxLength={100} /></div>
          <div><label htmlFor="g-disc" className="label">Max sconto %</label><input id="g-disc" inputMode="decimal" className={`field text-right ${bad("Max sconto")}`} value={d.maxDiscount} onChange={(e) => set({ maxDiscount: e.target.value })} placeholder="0" aria-invalid={numberError(d.maxDiscount, { max: 100 }) ? true : undefined} /></div>
          <div><label htmlFor="g-signed" className="label">Prezzo firmato (€)</label><input id="g-signed" inputMode="decimal" className={`field text-right ${bad("Prezzo firmato")}`} value={d.signedPrice} onChange={(e) => set({ signedPrice: e.target.value })} placeholder="Non ancora firmato" aria-invalid={numberError(d.signedPrice) ? true : undefined} /></div>
        </div>
        {d.mode === "percent" && <p className="mt-3 text-xs text-muted">In questa modalità ogni riga ha una percentuale per ogni mese: i giorni sono % × giorni lavorativi del mese intero.</p>}
      </section>

      <details className="card p-4 sm:p-5">
        <summary className="cursor-pointer text-lg font-medium tracking-normal">Giorni non lavorativi per mese</summary>
        <p className="mb-4 mt-2 text-sm text-muted">Festività e chiusure di questo progetto. Se lasci vuoto si usa il calendario generale (il valore proposto è nel campo).</p>
        {months.length === 0 ? <p className="text-sm text-muted">Indica prima il periodo.</p> : (
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-6">
            {months.map((mo, i) => {
              const effective = calc?.months.find((x) => x.month === mo);
              return (
                <div key={mo}><label htmlFor={`nw-${mo}`} className="label">{monthLabel(mo)}</label>
                  <input id={`nw-${mo}`} inputMode="numeric" className={`field text-right tnum ${bad(`nw-${mo}`)}`} value={d.nonWorking[mo] ?? ""} placeholder={effective ? String(effective.non_working) : "auto"}
                    onChange={(e) => update((x) => ({ ...x, nonWorking: { ...x.nonWorking, [mo]: e.target.value } }))} />
                  {effective && <p className="mt-1 text-[11px] text-muted tnum">{effective.work_days} lavorativi{i < 0 ? "" : ""}</p>}
                </div>
              );
            })}
          </div>
        )}
      </details>

      <details className="card p-4 sm:p-5">
        <summary className="cursor-pointer text-lg font-medium tracking-normal">Milestone e note</summary>
        <div className="mt-4 space-y-3">
          {d.milestones.map((ms, i) => (
            <div key={ms.key} className="flex flex-wrap items-end gap-3">
              <div><label htmlFor={`ms-m-${ms.key}`} className="label">Mese</label>
                <select id={`ms-m-${ms.key}`} className="field" value={ms.month} onChange={(e) => update((x) => m.updateMilestone(x, ms.key, { month: e.target.value }))}>
                  {[...new Set([...months, ms.month])].map((mo) => <option key={mo} value={mo}>{monthLabel(mo)}</option>)}
                </select></div>
              <div className="min-w-[12rem] flex-1"><label htmlFor={`ms-l-${ms.key}`} className="label">Milestone {i + 1}</label><input id={`ms-l-${ms.key}`} className="field" value={ms.label} maxLength={200} onChange={(e) => update((x) => m.updateMilestone(x, ms.key, { label: e.target.value }))} placeholder="es. Go-live" /></div>
              <button type="button" className="rounded-lg px-3 py-2 text-sm font-medium text-red-700 hover:bg-red-50" onClick={() => update((x) => m.removeMilestone(x, ms.key))}>Rimuovi<span className="sr-only"> milestone {i + 1}</span></button>
            </div>
          ))}
          <button type="button" disabled={months.length === 0} className="text-sm font-medium text-teal-700 underline-offset-4 hover:underline disabled:opacity-50" onClick={() => update((x) => m.addMilestone(x, months[0]))}>+ Aggiungi una milestone</button>
          <div><label htmlFor="g-notes" className="label">Note interne</label><textarea id="g-notes" className="field min-h-24" value={d.notes} maxLength={5000} onChange={(e) => set({ notes: e.target.value })} /></div>
        </div>
      </details>
    </div>
  );
}
