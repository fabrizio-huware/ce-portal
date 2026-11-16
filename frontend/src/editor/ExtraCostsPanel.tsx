import type { Calculation } from "../api/types";
import { Menu } from "../components/ui/Menu";
import { money } from "../lib/format";
import { MAX_EXTRA_COSTS, sentExtraCosts, type Draft } from "./model";
import * as m from "./model";
import { numberError } from "./numbers";

const cell = "px-1.5 py-1.5 align-top";
const input = "field !px-2 !py-1.5";

/**
 * Costi vari del CE: descrizione, costo e ricarico % (sul costo). Il totale di riga (costo × (1 + ricarico))
 * lo calcola il server, come ogni altro numero: qui si mostra soltanto.
 */
export function ExtraCostsPanel({ draft, calc, stale, invalid, update }: {
  draft: Draft;
  calc: Calculation | undefined;
  stale: boolean;
  invalid: Set<string>;
  update: (fn: (d: Draft) => Draft) => void;
}) {
  const rows = draft.extraCosts;
  const sent = sentExtraCosts(draft);
  const dim = stale ? "opacity-50" : "";
  const totalOf = (key: string): string | undefined => {
    const i = sent.findIndex((e) => e.key === key);
    return i >= 0 ? calc?.extra_costs[i]?.revenue : undefined;
  };
  const extras = calc?.extras;

  return (
    <section aria-label="Costi vari" className="card overflow-hidden">
      <header className="border-b border-line bg-surface/60 px-3 py-3">
        <h3 className="text-base font-medium tracking-normal">Costi vari</h3>
        <p className="text-xs text-muted">
          Spese che non sono giornate (viaggi, licenze…). Il totale di riga è il costo più il ricarico sul costo e si somma ai ricavi del CE;
          la contingency non si applica.
        </p>
      </header>
      <div role="region" aria-label="Righe dei costi vari" tabIndex={0} className="relative overflow-x-auto">
        <table className="w-full min-w-[40rem] border-collapse">
          <thead className="border-b border-line">
            <tr>
              <th className="th">Descrizione</th><th className="th text-right">Costo €</th><th className="th text-right">Ricarico %</th>
              <th className="th text-right">Totale riga</th><th className="th"><span className="sr-only">Azioni</span></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line">
            {rows.map((row, i) => {
              const n = i + 1;
              const total = totalOf(row.key);
              return (
                <tr key={row.key}>
                  <td className={`${cell} min-w-[14rem]`}><input className={`${input} ${invalid.has(`xdesc-${row.key}`) ? "border-red-600" : ""}`} value={row.description} maxLength={300}
                    onChange={(e) => update((d) => m.updateExtraCost(d, row.key, { description: e.target.value }))} placeholder="Descrizione del costo" aria-label={`Descrizione del costo vario ${n}`} /></td>
                  <td className={`${cell} w-32`}><input inputMode="decimal" className={`${input} text-right tnum ${invalid.has(`xcost-${row.key}`) ? "border-red-600" : ""}`} value={row.cost}
                    onChange={(e) => update((d) => m.updateExtraCost(d, row.key, { cost: e.target.value }))} placeholder="0" aria-label={`Costo del costo vario ${n}`}
                    aria-invalid={numberError(row.cost, { max: 9999999999.99 }) ? true : undefined} /></td>
                  <td className={`${cell} w-28`}><input inputMode="decimal" className={`${input} text-right tnum ${invalid.has(`xmk-${row.key}`) ? "border-red-600" : ""}`} value={row.markup}
                    onChange={(e) => update((d) => m.updateExtraCost(d, row.key, { markup: e.target.value }))} placeholder="0" aria-label={`Ricarico del costo vario ${n}`}
                    aria-invalid={numberError(row.markup, { min: m.MIN_MARKUP, max: m.MAX_MARKUP }) ? true : undefined} /></td>
                  <td className={`${cell} whitespace-nowrap pt-3 text-right tnum text-sm ${dim}`}>{total !== undefined ? money(total) : "—"}</td>
                  <td className={cell}>
                    <Menu label={<><span aria-hidden>⋯</span><span className="sr-only">Azioni del costo vario {n}</span></>} items={[
                      ...(i > 0 ? [{ label: "Sposta su", onSelect: () => update((d) => m.moveExtraCost(d, row.key, -1)) }] : []),
                      ...(i < rows.length - 1 ? [{ label: "Sposta giù", onSelect: () => update((d) => m.moveExtraCost(d, row.key, 1)) }] : []),
                      { label: "Elimina la riga", onSelect: () => update((d) => m.removeExtraCost(d, row.key)) },
                    ]} />
                  </td>
                </tr>
              );
            })}
            {rows.length === 0 && <tr><td className="px-3 py-5 text-sm text-muted" colSpan={5}>Nessun costo vario.</td></tr>}
          </tbody>
          {extras && sent.length > 0 && (
            <tfoot className={`border-t border-ink/20 bg-surface/60 ${dim}`}>
              <tr>
                <td className="px-3 py-2.5 text-sm font-semibold">Totale costi vari</td>
                <td className="px-3 py-2.5 text-right text-sm tnum whitespace-nowrap text-muted">{money(extras.cost)}</td><td />
                <td className="px-3 py-2.5 text-right text-sm font-semibold tnum whitespace-nowrap">{money(extras.revenue)}</td><td />
              </tr>
            </tfoot>
          )}
        </table>
      </div>
      <div className="border-t border-line px-3 py-2.5">
        <button type="button" disabled={rows.length >= MAX_EXTRA_COSTS} className="text-sm font-medium text-teal-700 underline-offset-4 hover:underline disabled:cursor-not-allowed disabled:opacity-50"
          onClick={() => update((d) => m.addExtraCost(d))}>+ Aggiungi un costo vario</button>
      </div>
    </section>
  );
}
