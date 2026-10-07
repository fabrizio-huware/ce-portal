import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState, type FormEvent } from "react";

import { api, unwrap } from "../../api/client";
import { ensureOk } from "../../api/ensure";
import type { components } from "../../api/schema";
import { Problems } from "../../components/ActionsBar";
import { AdminHeader, AdminOnly } from "../../components/admin/AdminHeader";
import { ImportDialog } from "../../components/admin/ImportDialog";
import { Chip } from "../../components/ui/Badge";
import { Button } from "../../components/ui/Button";
import { CheckField, TextField } from "../../components/ui/Fields";
import { EmptyState, ErrorBox, Notice } from "../../components/ui/Feedback";
import { Modal } from "../../components/ui/Modal";
import { ScrollArea } from "../../components/ui/ScrollArea";
import { Spinner } from "../../components/ui/Spinner";
import { numberError, parseNumber, showNumber } from "../../editor/numbers";
import { useUrlFilters } from "../../hooks/useUrlFilters";
import { errorDetails, errorMessage } from "../../lib/errors";
import { money, pct } from "../../lib/format";

type Profile = components["schemas"]["ProfileOut"];

export function PricingPage() {
  return <AdminOnly><Pricing /></AdminOnly>;
}

function Pricing() {
  const qc = useQueryClient();
  const f = useUrlFilters();
  const list = useQuery({ queryKey: ["admin-profiles"], queryFn: async () => unwrap(await api.GET("/api/v1/profiles", { params: { query: {} } })) });
  const years = useMemo(() => [...new Set((list.data ?? []).flatMap((p) => p.rates.map((r) => r.year)))].sort(), [list.data]);
  const year = Number(f.get("anno")) || years.at(-1) || new Date().getFullYear();
  const [rateFor, setRateFor] = useState<Profile | null>(null);
  const [editing, setEditing] = useState<Profile | "new" | null>(null);
  const [importing, setImporting] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const refresh = () => { for (const k of ["admin-profiles", "profiles-active"]) void qc.invalidateQueries({ queryKey: [k] }); };
  const rateOf = (p: Profile) => p.rates.find((r) => r.year === year);

  return (
    <div>
      <AdminHeader subtitle="Profili professionali e tariffe per anno. I CE già creati conservano le tariffe con cui sono nati: per aggiornarli si usa «Riallinea» dal dettaglio del CE." actions={<>
        <Button variant="secondary" onClick={() => setImporting(true)}>Importa il listino da CSV</Button>
        <Button variant="accent" onClick={() => setEditing("new")}>+ Nuovo profilo</Button></>} />
      <section aria-label="Anno" className="card mb-6 flex flex-wrap items-end gap-4 p-4">
        <TextField id="p-year" label="Anno delle tariffe" type="number" min={2000} max={2100} className="w-40" value={year} onChange={(e) => f.set({ anno: e.target.value || null })} />
        {years.length > 0 && <div className="flex flex-wrap items-center gap-2 pb-1 text-sm"><span className="text-muted">Anni con tariffe:</span>
          {years.map((y) => <button key={y} onClick={() => f.set({ anno: String(y) })} aria-pressed={y === year} className={`rounded-full border px-3 py-1 ${y === year ? "border-ink bg-ink text-paper" : "border-line hover:bg-surface"}`}>{y}</button>)}</div>}
      </section>
      {notice && <div className="mb-4"><Notice tone="ok">{notice}</Notice></div>}
      {list.isPending ? <div className="py-12 text-center"><Spinner label="Caricamento del listino…" /></div>
        : list.isError ? <ErrorBox message={errorMessage(list.error)} onRetry={() => list.refetch()} />
        : list.data.length === 0 ? <EmptyState title="Nessun profilo">Aggiungi un profilo o importa il listino da un file CSV.</EmptyState> : (
        <ScrollArea label={`Listino ${year}`} className="card">
          <table className="w-full min-w-[52rem] border-collapse">
            <caption className="sr-only">Listino {year}</caption>
            <thead className="border-b border-line bg-surface/60"><tr><th scope="col" className="th">Profilo</th><th scope="col" className="th">Fascia</th><th scope="col" className="th text-right">Prezzo/giorno</th><th scope="col" className="th text-right">Costo/giorno</th><th scope="col" className="th text-right">Margine</th><th scope="col" className="th"><span className="sr-only">Azioni</span></th></tr></thead>
            <tbody className="divide-y divide-line">
              {list.data.map((p) => {
                const r = rateOf(p);
                return (
                  <tr key={p.id}>
                    <th scope="row" className="td text-left font-medium"><span className="flex flex-wrap items-center gap-2">{p.name}{p.is_external && <Chip>esterno</Chip>}{!p.is_active && <Chip>disattivato</Chip>}</span></th>
                    <td className="td">{p.band ?? "—"}</td>
                    <td className="td whitespace-nowrap text-right tnum">{r ? money(r.daily_price) : <span className="text-muted">nessuna tariffa</span>}</td>
                    <td className="td whitespace-nowrap text-right tnum">{r ? money(r.daily_cost) : "—"}</td>
                    <td className="td whitespace-nowrap text-right tnum">{r && Number(r.daily_price) > 0 ? pct((Number(r.daily_price) - Number(r.daily_cost)) / Number(r.daily_price)) : "—"}</td>
                    <td className="td whitespace-nowrap text-right"><span className="flex justify-end gap-2">
                      <Button size="sm" variant="secondary" onClick={() => setRateFor(p)}>Tariffa {year}<span className="sr-only"> di {p.name}</span></Button>
                      <Button size="sm" variant="ghost" onClick={() => setEditing(p)}>Profilo<span className="sr-only"> {p.name}</span></Button></span></td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </ScrollArea>
      )}
      <RateForm profile={rateFor} year={year} onClose={() => setRateFor(null)} onSaved={(m) => { setRateFor(null); setNotice(m); refresh(); }} />
      <ProfileForm editing={editing} onClose={() => setEditing(null)} onSaved={(m) => { setEditing(null); setNotice(m); refresh(); }} />
      <ImportDialog open={importing} onClose={() => setImporting(false)} title="Importa il listino" path="/api/v1/profiles/import-rates" example="/esempi/listino.csv" onDone={() => { refresh(); setNotice("Listino importato."); }}
        columns={<><code>Profilo</code>; <code>Anno</code>; <code>Prezzo giorno</code>; <code>Costo giorno</code></>}
        note="Crea i profili mancanti e crea o aggiorna la tariffa di quell'anno. Importi con virgola decimale (1.800,00)." />
    </div>
  );
}

function RateForm({ profile, year, onClose, onSaved }: { profile: Profile | null; year: number; onClose: () => void; onSaved: (m: string) => void }) {
  const existing = profile?.rates.find((r) => r.year === year);
  const [v, setV] = useState({ price: "", cost: "" });
  const [seen, setSeen] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<{ message: string; issues: string[] } | null>(null);
  const key = profile ? `${profile.id}:${year}` : null;
  if (key !== seen) { setSeen(key); setError(null); setV({ price: showNumber(existing?.daily_price.replace(/\.?0+$/, "")), cost: showNumber(existing?.daily_cost.replace(/\.?0+$/, "")) }); }
  const pe = numberError(v.price), ce = numberError(v.cost);
  const valid = v.price.trim() !== "" && v.cost.trim() !== "" && !pe && !ce;
  async function save(e: FormEvent) {
    e.preventDefault(); if (!profile || !valid) return;
    setBusy(true); setError(null);
    try {
      unwrap(await api.PUT("/api/v1/profiles/{profile_id}/rates/{year}", { params: { path: { profile_id: profile.id, year } }, body: { daily_price: parseNumber(v.price)!, daily_cost: parseNumber(v.cost)! } }));
      onSaved(`Tariffa ${year} di ${profile.name} salvata.`);
    } catch (err) { setError(errorDetails(err)); } finally { setBusy(false); }
  }
  async function remove() {
    if (!profile) return;
    setBusy(true); setError(null);
    try { ensureOk(await api.DELETE("/api/v1/profiles/{profile_id}/rates/{year}", { params: { path: { profile_id: profile.id, year } } })); onSaved(`Tariffa ${year} di ${profile.name} eliminata.`); }
    catch (err) { setError(errorDetails(err)); } finally { setBusy(false); }
  }
  return (
    <Modal open={profile !== null} title={`Tariffa ${year} · ${profile?.name ?? ""}`} onClose={onClose}>
      <form onSubmit={save} className="space-y-4">
        <Problems error={error} />
        <div className="grid gap-4 sm:grid-cols-2">
          <TextField id="rf-price" label="Prezzo al giorno (€)" inputMode="decimal" required value={v.price} error={pe} onChange={(e) => setV({ ...v, price: e.target.value })} />
          <TextField id="rf-cost" label="Costo al giorno (€)" inputMode="decimal" required value={v.cost} error={ce} onChange={(e) => setV({ ...v, cost: e.target.value })} />
        </div>
        <p className="text-xs text-muted">Vale per i nuovi CE dell'anno {year}. I CE già creati non cambiano finché non li riallinei.</p>
        <div className="flex flex-wrap justify-between gap-2">
          <div>{existing && <Button type="button" variant="danger" size="sm" onClick={() => void remove()} disabled={busy}>Elimina la tariffa {year}</Button>}</div>
          <div className="flex gap-2"><Button type="button" variant="ghost" onClick={onClose}>Annulla</Button><Button type="submit" loading={busy} disabled={!valid}>Salva la tariffa</Button></div>
        </div>
      </form>
    </Modal>
  );
}

function ProfileForm({ editing, onClose, onSaved }: { editing: Profile | "new" | null; onClose: () => void; onSaved: (m: string) => void }) {
  const isNew = editing === "new";
  const p = editing && editing !== "new" ? editing : null;
  const blank = { name: "", external: false, order: "0", band: "", target: "", active: true };
  const [v, setV] = useState(blank);
  const [seen, setSeen] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<{ message: string; issues: string[] } | null>(null);
  if (editing !== seen) { setSeen(editing); setError(null); setV(p ? { name: p.name, external: p.is_external, order: String(p.sort_order), band: p.band ?? "", target: p.billability_target ? showNumber(p.billability_target.replace(/\.?0+$/, "")) : "", active: p.is_active } : blank); }
  const te = numberError(v.target, { max: 100 }), oe = numberError(v.order, { integer: true });
  async function submit(e: FormEvent) {
    e.preventDefault(); setBusy(true); setError(null);
    const body = { name: v.name.trim(), is_external: v.external, sort_order: Number(parseNumber(v.order) || 0), band: v.band.trim() || null, billability_target: parseNumber(v.target) || null };
    try {
      if (isNew) unwrap(await api.POST("/api/v1/profiles", { body }));
      else if (p) unwrap(await api.PATCH("/api/v1/profiles/{profile_id}", { params: { path: { profile_id: p.id } }, body: { ...body, is_active: v.active } }));
      onSaved(`${isNew ? "Profilo creato" : "Profilo aggiornato"}: ${body.name}.`);
    } catch (err) { setError(errorDetails(err)); } finally { setBusy(false); }
  }
  return (
    <Modal open={editing !== null} title={isNew ? "Nuovo profilo" : `Profilo ${p?.name ?? ""}`} onClose={onClose}>
      <form onSubmit={submit} className="space-y-4">
        <Problems error={error} />
        <TextField id="pf-name" label="Nome del profilo" required maxLength={100} value={v.name} onChange={(e) => setV({ ...v, name: e.target.value })} />
        <div className="grid gap-4 sm:grid-cols-3">
          <TextField id="pf-band" label="Fascia" maxLength={10} value={v.band} onChange={(e) => setV({ ...v, band: e.target.value })} />
          <TextField id="pf-order" label="Ordine" inputMode="numeric" value={v.order} error={oe} onChange={(e) => setV({ ...v, order: e.target.value })} />
          <TextField id="pf-target" label="Obiettivo fatturabilità %" inputMode="decimal" value={v.target} error={te} onChange={(e) => setV({ ...v, target: e.target.value })} />
        </div>
        <CheckField id="pf-ext" label="Profilo esterno (servizi esterni)" checked={v.external} onChange={(e) => setV({ ...v, external: e.target.checked })} hint="I suoi ricavi e costi vanno tra i «Servizi esterni» del CE." />
        {!isNew && <CheckField id="pf-active" label="Profilo attivo" checked={v.active} onChange={(e) => setV({ ...v, active: e.target.checked })} hint="Disattivato: non si può scegliere nelle nuove righe." />}
        <div className="flex justify-end gap-2"><Button type="button" variant="ghost" onClick={onClose}>Annulla</Button><Button type="submit" loading={busy} disabled={!v.name.trim() || !!te || !!oe}>{isNew ? "Crea il profilo" : "Salva"}</Button></div>
      </form>
    </Modal>
  );
}
