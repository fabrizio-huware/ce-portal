import type { Calculation } from "../api/types";
import { Menu } from "../components/ui/Menu";
import { month as monthLabel, money, num } from "../lib/format";
import { isGridPaste, type Draft, type LineDraft, type PhaseDraft } from "./model";
import * as m from "./model";
import { numberError } from "./numbers";

type Profile = { id: string; name: string; rates: { year: number }[] };
type Employee = { id: string; first_name: string; last_name: string; default_profile_id: string };

export type PhaseCardProps = {
  phase: PhaseDraft;
  index: number;
  count: number;
  mode: "hours" | "percent";
  months: string[];
  calc: Calculation | undefined;
  stale: boolean;
  profiles: Profile[];
  employees: Employee[];
  rateYear: number;
  invalid: Set<string>;
  update: (fn: (d: Draft) => Draft) => void;
  confirmRemove: (phaseKey: string) => void;
};

const cell = "px-1.5 py-1.5 align-top";
const input = "field !px-2 !py-1.5";

/** Con Invio si scende alla riga sotto nella stessa colonna (come in un foglio di calcolo); con Maiusc+Invio si sale. */
function onGridKey(e: React.KeyboardEvent<HTMLElement>) {
  if (e.key !== "Enter" || e.nativeEvent.isComposing) return;
  const el = e.target as HTMLElement;
  const col = el.dataset.col;
  if (!col) return;
  e.preventDefault();
  const scope = el.closest("[data-phase]");
  const all = Array.from(scope?.querySelectorAll<HTMLElement>(`[data-col="${col}"]`) ?? []);
  const next = all[all.indexOf(el) + (e.shiftKey ? -1 : 1)];
  next?.focus();
  if (next instanceof HTMLInputElement) next.select();
}

export function PhaseCard(p: PhaseCardProps) {
  const { phase, index, mode, months, calc, stale, profiles, employees, rateYear, invalid, update } = p;
  const pc = calc?.phases[index];
  const dim = stale ? "opacity-50" : "";
  const lineCalc = (j: number) => calc?.lines.find((l) => l.phase_index === index && l.line_index === j);
  const profileOk = (pr: Profile) => pr.rates.some((r) => r.year === rateYear);

  const pasteHandler = (lineKey: string, column: string) => (e: React.ClipboardEvent<HTMLInputElement>) => {
    const text = e.clipboardData.getData("text");
    if (!isGridPaste(text)) return; // un valore singolo si incolla normalmente
    e.preventDefault();
    update((d) => m.applyPaste(d, phase.key, lineKey, column, text, months));
  };

  const setLine = (line: LineDraft, patch: Partial<Omit<LineDraft, "key">>) => update((d) => m.updateLine(d, phase.key, line.key, patch));

  function chooseEmployee(line: LineDraft, employeeId: string) {
    const emp = employees.find((x) => x.id === employeeId);
    // Se la riga non aveva ancora un profilo (o un collaboratore) si propone quello del collaboratore.
    const adopt = emp && (!line.profileId || !line.employeeId) ? { profileId: emp.default_profile_id } : {};
    setLine(line, { employeeId, ...adopt });
  }

  return (
    <section data-phase={phase.key} aria-label={`Fase ${index + 1}`} className="card overflow-hidden">
      <header className="flex flex-wrap items-end gap-3 border-b border-line bg-surface/60 px-3 py-3">
        <div className="min-w-[12rem] flex-1">
          <label htmlFor={`ph-name-${phase.key}`} className="label">Fase {index + 1}</label>
          <input id={`ph-name-${phase.key}`} className={`${input} font-medium ${invalid.has(`phase-${phase.key}`) ? "border-red-600" : ""}`} value={phase.name}
            onChange={(e) => update((d) => m.updatePhase(d, phase.key, { name: e.target.value }))} placeholder="Nome della fase" maxLength={200} aria-label={`Nome della fase ${index + 1}`} />
        </div>
        <div className="w-32">
          <label htmlFor={`ph-cont-${phase.key}`} className="label">Contingency %</label>
          <input id={`ph-cont-${phase.key}`} inputMode="decimal" className={`${input} text-right ${invalid.has(`cont-${phase.key}`) ? "border-red-600" : ""}`} value={phase.contingency}
            onChange={(e) => update((d) => m.updatePhase(d, phase.key, { contingency: e.target.value }))} placeholder="0" aria-label={`Contingency della fase ${phase.name || index + 1}`}
            aria-invalid={numberError(phase.contingency, { max: 100 }) ? true : undefined} />
        </div>
        <Menu label={<><span aria-hidden>⋯</span><span className="sr-only">Azioni della fase {phase.name || index + 1}</span></>} items={[
          ...(index > 0 ? [{ label: "Sposta la fase in alto", onSelect: () => update((d) => m.movePhase(d, phase.key, -1)) }] : []),
          ...(index < p.count - 1 ? [{ label: "Sposta la fase in basso", onSelect: () => update((d) => m.movePhase(d, phase.key, 1)) }] : []),
          { label: "Elimina la fase", onSelect: () => (phase.lines.length ? p.confirmRemove(phase.key) : update((d) => m.removePhase(d, phase.key))) },
        ]} />
      </header>

      <p className="px-3 pt-2 text-[11px] text-muted md:hidden" aria-hidden>Scorri di lato per vedere ore, giorni e importi →</p>
      <div role="region" aria-label={`Righe della fase ${phase.name || index + 1}`} tabIndex={0} className="relative overflow-x-auto" onKeyDown={onGridKey}>
        <table className="w-full border-collapse" style={{ minWidth: mode === "hours" ? "62rem" : `${46 + months.length * 4.2}rem` }}>
          <thead className="border-b border-line">
            <tr>
              <th className="th">Attività</th><th className="th">Profilo</th><th className="th">Collaboratore</th><th className="th text-center">PM</th>
              {mode === "hours" ? <th className="th text-right">Ore</th> : months.map((mo) => <th key={mo} className="th text-right">{monthLabel(mo)}</th>)}
              <th className="th text-right">Giorni</th><th className="th text-right">Ricavo</th><th className="th text-right">Costo</th><th className="th"><span className="sr-only">Azioni</span></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line">
            {phase.lines.map((line, j) => {
              const c = lineCalc(j);
              const n = j + 1;
              return (
                <tr key={line.key}>
                  <td className={`${cell} min-w-[13rem]`}><input data-col="activity" className={`${input} ${invalid.has(`act-${line.key}`) ? "border-red-600" : ""}`} value={line.activity} maxLength={300}
                    onChange={(e) => setLine(line, { activity: e.target.value })} aria-label={`Attività ${n} della fase ${phase.name || index + 1}`} placeholder="Descrizione dell'attività" /></td>
                  <td className={`${cell} min-w-[10rem]`}>
                    <select className={`${input} ${invalid.has(`prof-${line.key}`) ? "border-red-600" : ""}`} value={line.profileId} onChange={(e) => setLine(line, { profileId: e.target.value })} aria-label={`Profilo ${n} della fase ${phase.name || index + 1}`}>
                      <option value="">Profilo…</option>
                      {profiles.map((pr) => <option key={pr.id} value={pr.id} disabled={!profileOk(pr) && pr.id !== line.profileId}>{pr.name}{profileOk(pr) ? "" : ` (senza tariffa ${rateYear})`}</option>)}
                    </select>
                  </td>
                  <td className={`${cell} min-w-[10rem]`}>
                    <select className={input} value={line.employeeId} onChange={(e) => chooseEmployee(line, e.target.value)} aria-label={`Collaboratore ${n} della fase ${phase.name || index + 1}`}>
                      <option value="">—</option>
                      {employees.map((e) => <option key={e.id} value={e.id}>{e.last_name} {e.first_name}</option>)}
                    </select>
                  </td>
                  <td className={`${cell} text-center`}><input type="checkbox" className="mt-2 h-4 w-4 accent-ink" checked={line.isPm} onChange={(e) => setLine(line, { isPm: e.target.checked })} aria-label={`Project management, riga ${n} della fase ${phase.name || index + 1}`} /></td>
                  {mode === "hours" ? (
                    <td className={`${cell} w-24`}><input data-col="hours" inputMode="decimal" className={`${input} text-right tnum ${invalid.has(`hours-${line.key}`) ? "border-red-600" : ""}`} value={line.hours}
                      onChange={(e) => setLine(line, { hours: e.target.value })} onPaste={pasteHandler(line.key, "hours")} aria-label={`Ore ${n} della fase ${phase.name || index + 1}`}
                      aria-invalid={numberError(line.hours, { decimals: 2 }) ? true : undefined} placeholder="0" /></td>
                  ) : months.map((mo) => (
                    <td key={mo} className={`${cell} w-[4.4rem]`}><input data-col={mo} inputMode="decimal" className={`${input} text-right tnum ${invalid.has(`alloc-${line.key}-${mo}`) ? "border-red-600" : ""}`} value={line.alloc[mo] ?? ""}
                      onChange={(e) => setLine(line, { alloc: { ...line.alloc, [mo]: e.target.value } })} onPaste={pasteHandler(line.key, mo)} placeholder="%"
                      aria-label={`Percentuale di ${monthLabel(mo)}, riga ${n} della fase ${phase.name || index + 1}`} /></td>
                  ))}
                  <td className={`${cell} whitespace-nowrap pt-3 text-right tnum text-sm ${dim}`}>{c ? num(c.days) : "—"}</td>
                  <td className={`${cell} whitespace-nowrap pt-3 text-right tnum text-sm ${dim}`}>{c ? money(c.revenue) : "—"}</td>
                  <td className={`${cell} whitespace-nowrap pt-3 text-right tnum text-sm ${dim}`}>{c ? money(c.cost) : "—"}</td>
                  <td className={cell}>
                    <Menu label={<><span aria-hidden>⋯</span><span className="sr-only">Azioni della riga {n} della fase {phase.name || index + 1}</span></>} items={[
                      ...(j > 0 ? [{ label: "Sposta su", onSelect: () => update((d) => m.moveLine(d, phase.key, line.key, -1)) }] : []),
                      ...(j < phase.lines.length - 1 ? [{ label: "Sposta giù", onSelect: () => update((d) => m.moveLine(d, phase.key, line.key, 1)) }] : []),
                      { label: "Duplica la riga", onSelect: () => update((d) => m.duplicateLine(d, phase.key, line.key)) },
                      { label: "Elimina la riga", onSelect: () => update((d) => m.removeLine(d, phase.key, line.key)) },
                    ]} />
                  </td>
                </tr>
              );
            })}
            {phase.lines.length === 0 && <tr><td className="px-3 py-5 text-sm text-muted" colSpan={9 + (mode === "hours" ? 0 : months.length - 1)}>Nessuna riga: aggiungine una.</td></tr>}
          </tbody>
          {pc && phase.lines.length > 0 && (
            <tfoot className={`border-t border-ink/20 bg-surface/60 ${dim}`}>
              <tr>
                <td className="px-3 py-2.5 text-sm font-semibold" colSpan={mode === "hours" ? 4 : 4}>Totale fase</td>
                {mode === "hours" ? <td className="px-3 py-2.5 text-right text-sm font-semibold tnum">{num(pc.hours)}</td> : <td colSpan={months.length} className="px-3 py-2.5 text-right text-sm text-muted tnum">{num(pc.hours)} ore</td>}
                <td className="px-3 py-2.5 text-right text-sm font-semibold tnum">{num(pc.days)}</td>
                <td className="px-3 py-2.5 text-right text-sm font-semibold tnum whitespace-nowrap">{money(pc.revenue)}</td>
                <td className="px-3 py-2.5 text-right text-sm font-semibold tnum whitespace-nowrap">{money(pc.cost)}</td><td />
              </tr>
              {Number(pc.contingency_revenue) > 0 && (
                <tr><td className="px-3 pb-2.5 text-sm text-muted" colSpan={mode === "hours" ? 6 : 5 + months.length}>Ricavo da contingency (senza costi)</td>
                  <td className="px-3 pb-2.5 text-right text-sm tnum whitespace-nowrap">{money(pc.contingency_revenue)}</td><td colSpan={2} /></tr>
              )}
            </tfoot>
          )}
        </table>
      </div>
      <div className="border-t border-line px-3 py-2.5">
        <button type="button" className="text-sm font-medium text-teal-700 underline-offset-4 hover:underline" onClick={() => update((d) => m.addLine(d, phase.key))}>+ Aggiungi una riga a questa fase</button>
      </div>
    </section>
  );
}
