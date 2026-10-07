import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";

import { api, unwrap } from "../../api/client";
import { ensureOk } from "../../api/ensure";
import type { components } from "../../api/schema";
import { Problems } from "../../components/ActionsBar";
import { AdminHeader, AdminOnly } from "../../components/admin/AdminHeader";
import { ImportDialog } from "../../components/admin/ImportDialog";
import { Chip } from "../../components/ui/Badge";
import { Button } from "../../components/ui/Button";
import { SelectField, TextField } from "../../components/ui/Fields";
import { EmptyState, ErrorBox, Notice } from "../../components/ui/Feedback";
import { Modal } from "../../components/ui/Modal";
import { ScrollArea } from "../../components/ui/ScrollArea";
import { Spinner } from "../../components/ui/Spinner";
import { useUrlFilters } from "../../hooks/useUrlFilters";
import { errorDetails, errorMessage } from "../../lib/errors";
import { date } from "../../lib/format";

type Day = components["schemas"]["NonWorkingDayOut"];
type Kind = "holiday" | "company_closure";
const KIND: Record<Kind, string> = { holiday: "Festività", company_closure: "Chiusura aziendale" };
const weekday = (iso: string) => new Date(`${iso}T00:00:00Z`).toLocaleDateString("it-IT", { weekday: "long", timeZone: "UTC" });

export function CalendarPage() {
  return <AdminOnly><Calendar /></AdminOnly>;
}

function Calendar() {
  const qc = useQueryClient();
  const f = useUrlFilters();
  const year = Number(f.get("anno")) || new Date().getFullYear();
  const list = useQuery({ queryKey: ["admin-calendar", year], queryFn: async () => unwrap(await api.GET("/api/v1/calendar", { params: { query: { year } } })) });
  const [editing, setEditing] = useState<Day | "new" | null>(null);
  const [removing, setRemoving] = useState<Day | null>(null);
  const [importing, setImporting] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [problem, setProblem] = useState<{ message: string; issues: string[] } | null>(null);
  const [busy, setBusy] = useState(false);
  const refresh = () => void qc.invalidateQueries({ queryKey: ["admin-calendar"] });

  async function generate() {
    setBusy(true); setProblem(null); setNotice(null);
    try {
      const r = unwrap(await api.POST("/api/v1/calendar/generate-holidays", { body: { year } }));
      setNotice(r.created === 0 ? `Le festività ${year} erano già tutte presenti.` : `Aggiunte ${r.created} festività per il ${year}.`);
      refresh();
    } catch (e) { setProblem(errorDetails(e)); } finally { setBusy(false); }
  }
  async function remove() {
    if (!removing) return;
    setBusy(true);
    try { ensureOk(await api.DELETE("/api/v1/calendar/{day_id}", { params: { path: { day_id: removing.id } } })); setNotice(`Eliminato il ${date(removing.day)}.`); setRemoving(null); refresh(); }
    catch (e) { setProblem(errorDetails(e)); setRemoving(null); } finally { setBusy(false); }
  }
  return (
    <div>
      <AdminHeader subtitle="Festività e chiusure aziendali. Servono a calcolare i giorni lavorativi dei CE nuovi; i CE già creati restano com'erano finché non li riallinei." actions={<>
        <Button variant="secondary" loading={busy} onClick={() => void generate()}>Genera le festività {year}</Button>
        <Button variant="secondary" onClick={() => setImporting(true)}>Importa chiusure da CSV</Button>
        <Button variant="accent" onClick={() => setEditing("new")}>+ Aggiungi un giorno</Button></>} />
      <section aria-label="Anno" className="card mb-6 p-4"><TextField id="cal-year" label="Anno" type="number" min={2000} max={2100} className="w-40" value={year} onChange={(e) => f.set({ anno: e.target.value || null })} /></section>
      {notice && <div className="mb-4"><Notice tone="ok">{notice}</Notice></div>}
      {problem && <div className="mb-4"><Problems error={problem} /></div>}
      {list.isPending ? <div className="py-12 text-center"><Spinner label="Caricamento del calendario…" /></div>
        : list.isError ? <ErrorBox message={errorMessage(list.error)} onRetry={() => list.refetch()} />
        : list.data.length === 0 ? <EmptyState title={`Nessun giorno nel ${year}`}>Usa «Genera le festività {String(year)}» per aggiungere le festività italiane, poi le chiusure aziendali.</EmptyState> : (
        <>
          <p aria-live="polite" className="mb-3 text-sm text-muted"><strong className="text-ink">{list.data.length}</strong> giorni nel {year}</p>
          <ScrollArea label={`Giorni non lavorativi ${year}`} className="card">
            <table className="w-full min-w-[40rem] border-collapse">
              <thead className="border-b border-line bg-surface/60"><tr><th className="th">Data</th><th className="th">Giorno</th><th className="th">Tipo</th><th className="th">Descrizione</th><th className="th"><span className="sr-only">Azioni</span></th></tr></thead>
              <tbody className="divide-y divide-line">
                {list.data.map((d) => (
                  <tr key={d.id}><td className="td whitespace-nowrap font-medium tnum">{date(d.day)}</td><td className="td capitalize text-muted">{weekday(d.day)}</td>
                    <td className="td">{d.kind === "holiday" ? <Chip>Festività</Chip> : <Chip tone="cyan">Chiusura aziendale</Chip>}</td><td className="td">{d.description}</td>
                    <td className="td text-right"><span className="flex justify-end gap-2"><Button size="sm" variant="secondary" onClick={() => setEditing(d)}>Modifica<span className="sr-only"> il {date(d.day)}</span></Button>
                      <Button size="sm" variant="ghost" onClick={() => setRemoving(d)}>Elimina<span className="sr-only"> il {date(d.day)}</span></Button></span></td></tr>
                ))}
              </tbody>
            </table>
          </ScrollArea>
        </>
      )}
      <DayForm editing={editing} year={year} onClose={() => setEditing(null)} onSaved={(m) => { setEditing(null); setNotice(m); refresh(); }} />
      <Modal open={removing !== null} title="Elimina il giorno" onClose={() => setRemoving(null)} footer={<><Button variant="ghost" onClick={() => setRemoving(null)}>Annulla</Button><Button variant="danger" loading={busy} onClick={() => void remove()}>Elimina</Button></>}>
        <p>Eliminare «{removing?.description}» del {removing ? date(removing.day) : ""}? Ai CE già creati non cambia nulla.</p>
      </Modal>
      <ImportDialog open={importing} onClose={() => setImporting(false)} title="Importa le chiusure aziendali" path="/api/v1/calendar/import" example="/esempi/chiusure.csv" onDone={() => { refresh(); setNotice("Chiusure importate."); }}
        columns={<><code>Data</code> (gg/mm/aaaa); <code>Descrizione</code> (facoltativa)</>} note="Aggiunge chiusure aziendali. Le date già presenti (anche le festività) restano invariate." />
    </div>
  );
}

function DayForm({ editing, year, onClose, onSaved }: { editing: Day | "new" | null; year: number; onClose: () => void; onSaved: (m: string) => void }) {
  const isNew = editing === "new";
  const day = editing && editing !== "new" ? editing : null;
  const [v, setV] = useState({ day: "", kind: "company_closure" as Kind, description: "" });
  const [seen, setSeen] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<{ message: string; issues: string[] } | null>(null);
  if (editing !== seen) { setSeen(editing); setError(null); setV(day ? { day: day.day, kind: day.kind as Kind, description: day.description } : { day: `${year}-01-01`, kind: "company_closure", description: "" }); }
  async function submit(e: FormEvent) {
    e.preventDefault(); setBusy(true); setError(null);
    try {
      if (isNew) unwrap(await api.POST("/api/v1/calendar", { body: { day: v.day, kind: v.kind, description: v.description.trim() } }));
      else if (day) unwrap(await api.PATCH("/api/v1/calendar/{day_id}", { params: { path: { day_id: day.id } }, body: { kind: v.kind, description: v.description.trim() } }));
      onSaved(isNew ? `Aggiunto il ${date(v.day)}.` : `Aggiornato il ${date(v.day)}.`);
    } catch (err) { setError(errorDetails(err)); } finally { setBusy(false); }
  }
  return (
    <Modal open={editing !== null} title={isNew ? "Aggiungi un giorno" : `Modifica il ${day ? date(day.day) : ""}`} onClose={onClose}>
      <form onSubmit={submit} className="space-y-4">
        <Problems error={error} />
        {isNew ? <TextField id="df-day" label="Data" type="date" required value={v.day} onChange={(e) => setV({ ...v, day: e.target.value })} /> : <p className="text-muted">{date(v.day)}</p>}
        <SelectField id="df-kind" label="Tipo" value={v.kind} onChange={(e) => setV({ ...v, kind: e.target.value as Kind })}>{(Object.keys(KIND) as Kind[]).map((k) => <option key={k} value={k}>{KIND[k]}</option>)}</SelectField>
        <TextField id="df-desc" label="Descrizione" required maxLength={200} value={v.description} onChange={(e) => setV({ ...v, description: e.target.value })} />
        <div className="flex justify-end gap-2"><Button type="button" variant="ghost" onClick={onClose}>Annulla</Button><Button type="submit" loading={busy} disabled={!v.day || !v.description.trim()}>{isNew ? "Aggiungi" : "Salva"}</Button></div>
      </form>
    </Modal>
  );
}
