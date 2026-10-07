import { keepPreviousData, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";

import { api, unwrap } from "../../api/client";
import { useProfiles } from "../../api/lookups";
import type { components } from "../../api/schema";
import { Problems } from "../../components/ActionsBar";
import { AdminHeader, AdminOnly } from "../../components/admin/AdminHeader";
import { ImportDialog } from "../../components/admin/ImportDialog";
import { Chip } from "../../components/ui/Badge";
import { Button } from "../../components/ui/Button";
import { CheckField, SelectField, TextField } from "../../components/ui/Fields";
import { EmptyState, ErrorBox, Notice } from "../../components/ui/Feedback";
import { Modal } from "../../components/ui/Modal";
import { Pagination } from "../../components/ui/Pagination";
import { ScrollArea } from "../../components/ui/ScrollArea";
import { Spinner } from "../../components/ui/Spinner";
import { useTextParam, useUrlFilters } from "../../hooks/useUrlFilters";
import { errorDetails, errorMessage } from "../../lib/errors";

type Employee = components["schemas"]["EmployeeOut"];
const LIMIT = 50;

export function EmployeesPage() {
  return <AdminOnly><Employees /></AdminOnly>;
}

function Employees() {
  const f = useUrlFilters();
  const profiles = useProfiles();
  const [q, setQ] = useTextParam(f, "q");
  const [editing, setEditing] = useState<Employee | "new" | null>(null);
  const [importing, setImporting] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const active = f.get("stato");
  const query = { ...(f.get("q") && { q: f.get("q") }), ...(f.get("profilo") && { profile_id: f.get("profilo") }), ...(active && { is_active: active === "1" }), limit: LIMIT, offset: (f.page - 1) * LIMIT };
  const list = useQuery({ queryKey: ["admin-employees", query], placeholderData: keepPreviousData, queryFn: async () => unwrap(await api.GET("/api/v1/employees", { params: { query } })) });
  const qc = useQueryClient();
  const refresh = () => { for (const k of ["admin-employees", "employees-active"]) void qc.invalidateQueries({ queryKey: [k] }); };
  return (
    <div>
      <AdminHeader subtitle="Le persone che si possono assegnare alle righe dei CE. Un collaboratore non si elimina: si disattiva." actions={<>
        <Button variant="secondary" onClick={() => setImporting(true)}>Importa da CSV</Button>
        <Button variant="accent" onClick={() => setEditing("new")}>+ Nuovo collaboratore</Button></>} />
      <section aria-label="Filtri" className="card mb-6 grid gap-4 p-4 sm:grid-cols-3">
        <TextField id="e-q" label="Cerca per nome" value={q} onChange={(e) => setQ(e.target.value)} />
        <SelectField id="e-profile" label="Profilo" value={f.get("profilo")} onChange={(e) => f.set({ profilo: e.target.value || null })}><option value="">Tutti</option>{profiles.data?.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}</SelectField>
        <SelectField id="e-active" label="Stato" value={active} onChange={(e) => f.set({ stato: e.target.value || null })}><option value="">Tutti</option><option value="1">Attivi</option><option value="0">Disattivati</option></SelectField>
      </section>
      {notice && <div className="mb-4"><Notice tone="ok">{notice}</Notice></div>}
      {list.isPending ? <div className="py-12 text-center"><Spinner label="Caricamento dei collaboratori…" /></div>
        : list.isError ? <ErrorBox message={errorMessage(list.error)} onRetry={() => list.refetch()} />
        : list.data.items.length === 0 ? <EmptyState title="Nessun collaboratore">Cambia i filtri, aggiungine uno o importa un file CSV.</EmptyState> : (
        <>
          <p aria-live="polite" className="mb-3 text-sm text-muted"><strong className="text-ink">{list.data.total}</strong> {list.data.total === 1 ? "collaboratore" : "collaboratori"}</p>
          <ScrollArea label="Elenco dei collaboratori" className="card">
            <table className="w-full min-w-[44rem] border-collapse">
              <thead className="border-b border-line bg-surface/60"><tr><th className="th">Cognome e nome</th><th className="th">Profilo</th><th className="th">NetSuite</th><th className="th">Jira</th><th className="th">Stato</th><th className="th"><span className="sr-only">Azioni</span></th></tr></thead>
              <tbody className="divide-y divide-line">
                {list.data.items.map((e) => (
                  <tr key={e.id}><td className="td font-medium">{e.last_name} {e.first_name}</td><td className="td">{e.profile_name}</td><td className="td">{e.netsuite_id ?? "—"}</td><td className="td">{e.jira_account_id ?? "—"}</td>
                    <td className="td">{e.is_active ? <Chip tone="cyan">Attivo</Chip> : <Chip>Disattivato</Chip>}</td>
                    <td className="td text-right"><Button size="sm" variant="secondary" onClick={() => setEditing(e)}>Modifica<span className="sr-only"> {e.last_name} {e.first_name}</span></Button></td></tr>
                ))}
              </tbody>
            </table>
          </ScrollArea>
          <Pagination total={list.data.total} limit={LIMIT} offset={(f.page - 1) * LIMIT} onChange={(o) => f.set({ page: String(o / LIMIT + 1) }, true)} />
        </>
      )}
      <EmployeeForm editing={editing} onClose={() => setEditing(null)} onSaved={(m) => { setEditing(null); setNotice(m); refresh(); }} />
      <ImportDialog open={importing} onClose={() => setImporting(false)} title="Importa collaboratori" path="/api/v1/employees/import" example="/esempi/collaboratori.csv" onDone={() => { refresh(); setNotice("Collaboratori importati."); }}
        columns={<><code>Nome</code>; <code>Cognome</code>; <code>Profilo</code>; <code>Attivo</code> (facoltative: <code>netsuite_id</code>, <code>jira_account_id</code>)</>}
        note="Crea o aggiorna per nome e cognome. Il profilo deve già esistere ed essere attivo. Senza la colonna «Attivo» i nuovi sono attivi e gli esistenti non cambiano." />
    </div>
  );
}

function EmployeeForm({ editing, onClose, onSaved }: { editing: Employee | "new" | null; onClose: () => void; onSaved: (m: string) => void }) {
  const profiles = useProfiles();
  const isNew = editing === "new";
  const emp = editing && editing !== "new" ? editing : null;
  const blank = { first: "", last: "", profile: "", netsuite: "", jira: "", active: true };
  const [v, setV] = useState(blank);
  const [seen, setSeen] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<{ message: string; issues: string[] } | null>(null);
  if (editing !== seen) {
    setSeen(editing); setError(null);
    setV(emp ? { first: emp.first_name, last: emp.last_name, profile: emp.default_profile_id, netsuite: emp.netsuite_id ?? "", jira: emp.jira_account_id ?? "", active: emp.is_active } : blank);
  }
  async function submit(e: FormEvent) {
    e.preventDefault(); setBusy(true); setError(null);
    const common = { first_name: v.first.trim(), last_name: v.last.trim(), default_profile_id: v.profile, netsuite_id: v.netsuite.trim() || null, jira_account_id: v.jira.trim() || null };
    try {
      if (isNew) unwrap(await api.POST("/api/v1/employees", { body: { ...common, is_active: v.active } }));
      else if (emp) unwrap(await api.PATCH("/api/v1/employees/{employee_id}", { params: { path: { employee_id: emp.id } }, body: { ...common, is_active: v.active } }));
      onSaved(`${isNew ? "Collaboratore creato" : "Collaboratore aggiornato"}: ${v.first.trim()} ${v.last.trim()}.`);
    } catch (err) { setError(errorDetails(err)); } finally { setBusy(false); }
  }
  return (
    <Modal open={editing !== null} title={isNew ? "Nuovo collaboratore" : `Modifica ${emp ? `${emp.first_name} ${emp.last_name}` : ""}`} onClose={onClose}>
      <form onSubmit={submit} className="space-y-4">
        <Problems error={error} />
        <div className="grid gap-4 sm:grid-cols-2">
          <TextField id="ef-first" label="Nome" required maxLength={100} value={v.first} onChange={(e) => setV({ ...v, first: e.target.value })} />
          <TextField id="ef-last" label="Cognome" required maxLength={100} value={v.last} onChange={(e) => setV({ ...v, last: e.target.value })} />
        </div>
        <SelectField id="ef-profile" label="Profilo di default" required value={v.profile} onChange={(e) => setV({ ...v, profile: e.target.value })} hint="Si propone quando lo scegli su una riga di un CE.">
          <option value="">Scegli il profilo…</option>{profiles.data?.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
        </SelectField>
        <div className="grid gap-4 sm:grid-cols-2">
          <TextField id="ef-ns" label="ID NetSuite (facoltativo)" maxLength={100} value={v.netsuite} onChange={(e) => setV({ ...v, netsuite: e.target.value })} />
          <TextField id="ef-jira" label="Account Jira (facoltativo)" maxLength={100} value={v.jira} onChange={(e) => setV({ ...v, jira: e.target.value })} />
        </div>
        <CheckField id="ef-active" label="Collaboratore attivo" checked={v.active} onChange={(e) => setV({ ...v, active: e.target.checked })} hint="Disattivato: non si può assegnare a nuove righe." />
        <div className="flex justify-end gap-2"><Button type="button" variant="ghost" onClick={onClose}>Annulla</Button><Button type="submit" loading={busy} disabled={!v.first.trim() || !v.last.trim() || !v.profile}>{isNew ? "Crea il collaboratore" : "Salva"}</Button></div>
      </form>
    </Modal>
  );
}
