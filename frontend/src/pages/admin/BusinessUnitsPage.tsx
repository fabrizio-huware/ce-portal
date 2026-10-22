import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";

import { api, unwrap } from "../../api/client";
import type { components } from "../../api/schema";
import { Problems } from "../../components/ActionsBar";
import { AdminHeader, AdminOnly } from "../../components/admin/AdminHeader";
import { Chip } from "../../components/ui/Badge";
import { Button } from "../../components/ui/Button";
import { CheckField, TextField } from "../../components/ui/Fields";
import { EmptyState, ErrorBox, Notice } from "../../components/ui/Feedback";
import { Modal } from "../../components/ui/Modal";
import { ScrollArea } from "../../components/ui/ScrollArea";
import { Spinner } from "../../components/ui/Spinner";
import { isSystemBusinessUnit } from "../../lib/businessUnits";
import { errorDetails, errorMessage } from "../../lib/errors";

type Unit = components["schemas"]["BusinessUnitOut"];

export function BusinessUnitsPage() {
  return <AdminOnly><BusinessUnits /></AdminOnly>;
}

function BusinessUnits() {
  const [editing, setEditing] = useState<Unit | "new" | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const list = useQuery({ queryKey: ["admin-business-units"], queryFn: async () => unwrap(await api.GET("/api/v1/business-units")) });
  const qc = useQueryClient();
  return (
    <div>
      <AdminHeader subtitle="Le business unit stanno sopra le practice: ogni practice ne ha una, ogni presale o responsabile ne ha una, e decidono chi vede un CE. Non si eliminano: si disattivano." actions={<Button variant="accent" onClick={() => setEditing("new")}>+ Nuova business unit</Button>} />
      {notice && <div className="mb-4"><Notice tone="ok">{notice}</Notice></div>}
      {list.isPending ? <div className="py-12 text-center"><Spinner label="Caricamento delle business unit…" /></div>
        : list.isError ? <ErrorBox message={errorMessage(list.error)} onRetry={() => list.refetch()} />
        : list.data.length === 0 ? <EmptyState title="Nessuna business unit">Aggiungine una con «Nuova business unit».</EmptyState> : (
        <>
          <p aria-live="polite" className="mb-3 text-sm text-muted"><strong className="text-ink">{list.data.length}</strong> business unit</p>
          <ScrollArea label="Elenco delle business unit" className="card">
            <table className="w-full min-w-[46rem] border-collapse">
              <thead className="border-b border-line bg-surface/60"><tr><th className="th">Nome</th><th className="th text-right">Practice</th><th className="th text-right">Collaboratori</th><th className="th text-right">Presale e responsabili</th><th className="th">Stato</th><th className="th"><span className="sr-only">Azioni</span></th></tr></thead>
              <tbody className="divide-y divide-line">
                {list.data.map((u) => (
                  <tr key={u.id}>
                    <td className="td font-medium">{u.name}{isSystemBusinessUnit(u.name) && <span className="block text-xs font-normal text-muted">Di sistema: accoglie le practice non ancora assegnate</span>}</td>
                    <td className="td text-right tnum">{u.practices_count}</td>
                    <td className="td text-right tnum">{u.employees_count}</td>
                    <td className="td text-right tnum">{u.users_count}</td>
                    <td className="td">{u.is_active ? <Chip tone="cyan">Attiva</Chip> : <Chip>Disattivata</Chip>}</td>
                    <td className="td text-right">{isSystemBusinessUnit(u.name) ? <span className="text-sm text-muted">—</span> : <Button size="sm" variant="secondary" onClick={() => setEditing(u)}>Modifica<span className="sr-only"> {u.name}</span></Button>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </ScrollArea>
        </>
      )}
      <BusinessUnitForm editing={editing} onClose={() => setEditing(null)} onSaved={(m) => { setEditing(null); setNotice(m); for (const k of ["admin-business-units", "business-units-lookup", "admin-practices", "admin-users"]) void qc.invalidateQueries({ queryKey: [k] }); }} />
    </div>
  );
}

function BusinessUnitForm({ editing, onClose, onSaved }: { editing: Unit | "new" | null; onClose: () => void; onSaved: (m: string) => void }) {
  const isNew = editing === "new";
  const unit = editing && editing !== "new" ? editing : null;
  const [v, setV] = useState({ name: "", active: true });
  const [seen, setSeen] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<{ message: string; issues: string[] } | null>(null);
  if (editing !== seen) {
    setSeen(editing); setError(null);
    setV(unit ? { name: unit.name, active: unit.is_active } : { name: "", active: true });
  }
  async function submit(e: FormEvent) {
    e.preventDefault(); setBusy(true); setError(null);
    const name = v.name.trim();
    try {
      if (isNew) unwrap(await api.POST("/api/v1/business-units", { body: { name } }));
      else if (unit) unwrap(await api.PATCH("/api/v1/business-units/{business_unit_id}", { params: { path: { business_unit_id: unit.id } }, body: { name, is_active: v.active } }));
      onSaved(isNew ? `Business unit creata: ${name}.` : `Business unit aggiornata: ${name}.`);
    } catch (err) { setError(errorDetails(err)); } finally { setBusy(false); }
  }
  return (
    <Modal open={editing !== null} title={isNew ? "Nuova business unit" : `Modifica ${unit?.name ?? ""}`} onClose={onClose}>
      <form onSubmit={submit} className="space-y-4">
        <Problems error={error} />
        <TextField id="bf-name" label="Nome della business unit" required maxLength={100} value={v.name} onChange={(e) => setV({ ...v, name: e.target.value })} />
        {!isNew && <CheckField id="bf-active" label="Business unit attiva" checked={v.active} onChange={(e) => setV({ ...v, active: e.target.checked })} hint="Disattivata: non si può scegliere per practice, persone o CE nuovi; chi la ha già la mantiene." />}
        <div className="flex justify-end gap-2"><Button type="button" variant="ghost" onClick={onClose}>Annulla</Button><Button type="submit" loading={busy} disabled={!v.name.trim()}>{isNew ? "Crea la business unit" : "Salva"}</Button></div>
      </form>
    </Modal>
  );
}
