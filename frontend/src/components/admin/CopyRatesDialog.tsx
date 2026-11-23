import { useState, type FormEvent } from "react";

import { api, unwrap } from "../../api/client";
import type { components } from "../../api/schema";
import { Problems } from "../ActionsBar";
import { numberError, parseNumber } from "../../editor/numbers";
import { errorDetails } from "../../lib/errors";
import { money } from "../../lib/format";
import { Button } from "../ui/Button";
import { TextField } from "../ui/Fields";
import { Notice } from "../ui/Feedback";
import { Modal } from "../ui/Modal";
import { ScrollArea } from "../ui/ScrollArea";

type Result = components["schemas"]["CopyRatesResult"];
const ACTION = { created: "nuova", updated: "sovrascritta", unchanged: "invariata" } as const;
const ADJUST = { min: -90, max: 100 };

/** Anni scritti a mano («2027, 2028» o «2027 2028»): interi tra 2000 e 2100, senza ripetizioni. */
export function parseYears(text: string): number[] | null {
  const parts = text.split(/[\s,;]+/).filter(Boolean);
  if (parts.length === 0 || parts.length > 10) return null;
  const years = parts.map((p) => (/^\d{4}$/.test(p) ? Number(p) : NaN));
  if (years.some((y) => !(y >= 2000 && y <= 2100)) || new Set(years).size !== years.length) return null;
  return years;
}

const plural = (n: number, one: string, many: string) => `${n} ${n === 1 ? one : many}`;

/**
 * Copia le tariffe di un anno su altri anni, con un adeguamento facoltativo in %. Prima l'anteprima
 * (nulla viene scritto), poi la conferma: le tariffe già presenti negli anni di arrivo sono sovrascritte.
 */
export function CopyRatesDialog({ open, fromYear, onClose, onDone }: { open: boolean; fromYear: number; onClose: () => void; onDone: (message: string) => void }) {
  const blank = { to: "", price: "", cost: "" };
  const [v, setV] = useState(blank);
  const [seen, setSeen] = useState(false);
  const [preview, setPreview] = useState<Result | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<{ message: string; issues: string[] } | null>(null);
  if (open !== seen) { setSeen(open); if (open) { setV(blank); setPreview(null); setError(null); } }

  const years = parseYears(v.to);
  const toError = v.to.trim() === "" ? null : !years ? "Scrivi da 1 a 10 anni di quattro cifre (2000-2100), separati da virgola" : years.includes(fromYear) ? "L'anno di arrivo non può essere quello di partenza" : null;
  const pe = numberError(v.price, ADJUST), ce = numberError(v.cost, ADJUST);
  const valid = !!years && !toError && !pe && !ce;
  const edit = (patch: Partial<typeof v>) => { setV({ ...v, ...patch }); setPreview(null); };
  const body = () => ({ from_year: fromYear, to_years: years!, price_adjust_pct: parseNumber(v.price, true) || "0", cost_adjust_pct: parseNumber(v.cost, true) || "0" });

  async function run(e: FormEvent | null, dryRun: boolean) {
    e?.preventDefault();
    if (!valid) return;
    setBusy(true); setError(null);
    try {
      const res = unwrap(await api.POST("/api/v1/profiles/copy-rates", { params: { query: { dry_run: dryRun } }, body: body() }));
      if (dryRun) setPreview(res);
      else onDone(`Tariffe ${fromYear} copiate su ${res.to_years.join(", ")}: ${plural(res.created, "creata", "create")}, ${plural(res.updated, "sovrascritta", "sovrascritte")}, ${plural(res.unchanged, "invariata", "invariate")}.`);
    } catch (err) { setError(errorDetails(err)); } finally { setBusy(false); }
  }

  return (
    <Modal open={open} title={`Copia le tariffe del ${fromYear}`} onClose={onClose}>
      <form onSubmit={(e) => void run(e, true)} className="space-y-4">
        <Problems error={error} />
        <TextField id="cr-to" label="Anni di arrivo" required inputMode="numeric" placeholder="2027, 2028" value={v.to} error={toError} hint="Uno o più anni, separati da virgola." onChange={(e) => edit({ to: e.target.value })} />
        <div className="grid gap-4 sm:grid-cols-2">
          <TextField id="cr-price" label="Adeguamento del prezzo (%)" inputMode="decimal" placeholder="0" value={v.price} error={pe} hint="Vuoto = identico. Per esempio 3 oppure -2,5." onChange={(e) => edit({ price: e.target.value })} />
          <TextField id="cr-cost" label="Adeguamento del costo (%)" inputMode="decimal" placeholder="0" value={v.cost} error={ce} hint="Vuoto = identico." onChange={(e) => edit({ cost: e.target.value })} />
        </div>
        <p className="text-xs text-muted">Le tariffe già presenti negli anni di arrivo vengono <strong>sovrascritte</strong>; i profili senza tariffa nel {fromYear} non si toccano. I CE già creati non cambiano finché non li riallinei.</p>

        {preview && (
          <section aria-label="Anteprima" className="space-y-3">
            <Notice tone={preview.updated > 0 ? "warn" : "info"}>
              Anteprima (nulla è stato scritto): {plural(preview.created, "tariffa nuova", "tariffe nuove")}, {plural(preview.updated, "sovrascritta", "sovrascritte")}, {plural(preview.unchanged, "invariata", "invariate")}.
            </Notice>
            <ScrollArea label="Anteprima della copia" className="max-h-72 overflow-y-auto rounded-xl border border-line">
              <table className="w-full min-w-[34rem] border-collapse text-sm">
                <thead className="border-b border-line bg-surface/60"><tr><th scope="col" className="th">Profilo</th><th scope="col" className="th">Anno</th><th scope="col" className="th text-right">Prezzo</th><th scope="col" className="th text-right">Costo</th><th scope="col" className="th">Esito</th></tr></thead>
                <tbody className="divide-y divide-line">
                  {preview.items.map((i) => (
                    <tr key={`${i.profile_id}-${i.year}`}>
                      <th scope="row" className="td text-left font-medium">{i.profile_name}</th>
                      <td className="td tnum">{i.year}</td>
                      <td className="td whitespace-nowrap text-right tnum">{i.old_price != null && i.action === "updated" && <span className="mr-1 text-muted line-through">{money(i.old_price)}</span>}{money(i.new_price)}</td>
                      <td className="td whitespace-nowrap text-right tnum">{i.old_cost != null && i.action === "updated" && <span className="mr-1 text-muted line-through">{money(i.old_cost)}</span>}{money(i.new_cost)}</td>
                      <td className="td">{ACTION[i.action as keyof typeof ACTION] ?? i.action}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </ScrollArea>
          </section>
        )}

        <div className="flex flex-wrap justify-end gap-2">
          <Button type="button" variant="ghost" onClick={onClose}>Annulla</Button>
          {preview ? <Button type="button" loading={busy} onClick={() => void run(null, false)}>Conferma e copia</Button>
            : <Button type="submit" loading={busy} disabled={!valid}>Mostra l'anteprima</Button>}
        </div>
      </form>
    </Modal>
  );
}
