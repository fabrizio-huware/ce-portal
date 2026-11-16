import type { Calculation } from "../api/types";
import { Menu } from "../components/ui/Menu";
import { money } from "../lib/format";
import { MAX_DISCOUNTS, sentDiscounts, type Draft } from "./model";
import * as m from "./model";
import { numberError } from "./numbers";

const cell = "px-1.5 py-1.5 align-top";
const input = "field !px-2 !py-1.5";

const ruleOf = (kind: m.DiscountKind) => (kind === "percent" ? { max: 100 } : { max: 9999999999.99 });

/**
 * Sconti del CE: descrizione e importo in euro oppure percentuale sul prezzo prima degli sconti. L'importo scontato
 * lo calcola il server, come ogni altro numero: qui si mostra soltanto. Tolgono dal prezzo, i costi non cambiano.
 */
export function DiscountsPanel({ draft, calc, stale, invalid, update }: {
  draft: Draft;
  calc: Calculation | undefined;
  stale: boolean;
  invalid: Set<string>;
  update: (fn: (d: Draft) => Draft) => void;
}) {
  const rows = draft.discounts;
  const sent = sentDiscounts(draft);
  const dim = stale ? "opacity-50" : "";
  const amountOf = (key: string): string | undefined => {
    const i = sent.findIndex((x) => x.key === key);
    return i >= 0 ? calc?.discount_items[i]?.amount : undefined;
  };
  const total = calc?.discounts;

  return (
    <section aria-label="Sconti" className="card overflow-hidden">
      <header className="border-b border-line bg-surface/60 px-3 py-3">
        <h3 className="text-base font-medium tracking-normal">Sconti</h3>
        <p className="text-xs text-muted">
          Importi in euro, oppure percentuali sul prezzo prima degli sconti (servizi, contingency e costi vari). Si tolgono dal prezzo progetto;
          i costi restano invariati e il margine si riduce.
        </p>
      </header>
      <div role="region" aria-label="Righe degli sconti" tabIndex={0} className="relative overflow-x-auto">
        <table className="w-full min-w-[40rem] border-collapse">
          <thead className="border-b border-line">
            <tr>
              <th className="th">Descrizione</th><th className="th">Tipo</th><th className="th text-right">Valore</th>
              <th className="th text-right">Sconto €</th><th className="th"><span className="sr-only">Azioni</span></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line">
            {rows.map((row, i) => {
              const n = i + 1;
              const amount = amountOf(row.key);
              return (
                <tr key={row.key}>
                  <td className={`${cell} min-w-[14rem]`}><input className={`${input} ${invalid.has(`ddesc-${row.key}`) ? "border-red-600" : ""}`} value={row.description} maxLength={300}
                    onChange={(e) => update((d) => m.updateDiscount(d, row.key, { description: e.target.value }))} placeholder="Descrizione dello sconto" aria-label={`Descrizione dello sconto ${n}`} /></td>
                  <td className={`${cell} w-40`}>
                    <select className={input} value={row.kind} aria-label={`Tipo dello sconto ${n}`}
                      onChange={(e) => update((d) => m.updateDiscount(d, row.key, { kind: e.target.value as m.DiscountKind }))}>
                      <option value="amount">Importo (€)</option>
                      <option value="percent">Percentuale (%)</option>
                    </select>
                  </td>
                  <td className={`${cell} w-32`}><input inputMode="decimal" className={`${input} text-right tnum ${invalid.has(`dval-${row.key}`) ? "border-red-600" : ""}`} value={row.value}
                    onChange={(e) => update((d) => m.updateDiscount(d, row.key, { value: e.target.value }))} placeholder="0"
                    aria-label={`${row.kind === "percent" ? "Percentuale" : "Importo"} dello sconto ${n}`}
                    aria-invalid={numberError(row.value, ruleOf(row.kind)) ? true : undefined} /></td>
                  <td className={`${cell} whitespace-nowrap pt-3 text-right tnum text-sm ${dim}`}>{amount !== undefined ? money(amount) : "—"}</td>
                  <td className={cell}>
                    <Menu label={<><span aria-hidden>⋯</span><span className="sr-only">Azioni dello sconto {n}</span></>} items={[
                      ...(i > 0 ? [{ label: "Sposta su", onSelect: () => update((d) => m.moveDiscount(d, row.key, -1)) }] : []),
                      ...(i < rows.length - 1 ? [{ label: "Sposta giù", onSelect: () => update((d) => m.moveDiscount(d, row.key, 1)) }] : []),
                      { label: "Elimina la riga", onSelect: () => update((d) => m.removeDiscount(d, row.key)) },
                    ]} />
                  </td>
                </tr>
              );
            })}
            {rows.length === 0 && <tr><td className="px-3 py-5 text-sm text-muted" colSpan={5}>Nessuno sconto.</td></tr>}
          </tbody>
          {total && sent.length > 0 && (
            <tfoot className={`border-t border-ink/20 bg-surface/60 ${dim}`}>
              <tr>
                <td className="px-3 py-2.5 text-sm font-semibold">Totale sconti</td><td /><td />
                <td className="px-3 py-2.5 text-right text-sm font-semibold tnum whitespace-nowrap">{money(String(-Number(total.revenue)))}</td><td />
              </tr>
            </tfoot>
          )}
        </table>
      </div>
      <div className="border-t border-line px-3 py-2.5">
        <button type="button" disabled={rows.length >= MAX_DISCOUNTS} className="text-sm font-medium text-teal-700 underline-offset-4 hover:underline disabled:cursor-not-allowed disabled:opacity-50"
          onClick={() => update((d) => m.addDiscount(d))}>+ Aggiungi uno sconto</button>
      </div>
    </section>
  );
}
