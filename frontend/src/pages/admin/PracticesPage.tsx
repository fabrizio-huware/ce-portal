import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";

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
import { errorDetails, errorMessage } from "../../lib/errors";
import { isSystemPractice } from "../../lib/practice";

type Practice = components["schemas"]["PracticeOut"];

export function PracticesPage() {
  return <AdminOnly><Practices /></AdminOnly>;
}

function Practices() {
  const [editing, setEditing] = useState<Practice | "new" | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const list = useQuery({ queryKey: ["admin-practices"], queryFn: async () => unwrap(await api.GET("/api/v1/practices")) });
  const qc = useQueryClient();
  return (
    <div>
      <AdminHeader subtitle="Le aree di competenza: ogni collaboratore ne ha una. Una practice non si elimina: si disattiva, così non si può più scegliere ma chi la ha già la mantiene." actions={<Button variant="accent" onClick={() => setEditing("new")}>+ Nuova practice</Button>} />
      {notice && <div className="mb-4"><Notice tone="ok">{notice}</Notice></div>}
      {list.isPending ? <div className="py-12 text-center"><Spinner label="Caricamento delle practice…" /></div>
        : list.isError ? <ErrorBox message={errorMessage(list.error)} onRetry={() => list.refetch()} />
        : list.data.length === 0 ? <EmptyState title="Nessuna practice">Aggiungine una con «Nuova practice».</EmptyState> : (
        <>
          <p aria-live="polite" className="mb-3 text-sm text-muted"><strong className="text-ink">{list.data.length}</strong> practice</p>
          <ScrollArea label="Elenco delle practice" className="card">
            <table className="w-full min-w-[36rem] border-collapse">
              <thead className="border-b border-line bg-surface/60"><tr><th className="th">Nome</th><th className="th text-right">Collaboratori attivi</th><th className="th">Stato</th><th className="th"><span className="sr-only">Azioni</span></th></tr></thead>
              <tbody className="divide-y divide-line">
                {list.data.map((p) => (
                  <tr key={p.id}>
                    <td className="td font-medium">{p.name}{isSystemPractice(p.name) && <span className="block text-xs font-normal text-muted">Di sistema: la ricevono i collaboratori finché non se ne sceglie una</span>}</td>
                    <td className="td text-right tnum">{p.employees_count > 0 ? <Link className="text-teal-700 underline" to={`/admin/collaboratori?practice=${p.id}`}>{p.employees_count}<span className="sr-only"> collaboratori di {p.name}</span></Link> : "0"}</td>
                    <td className="td">{p.is_active ? <Chip tone="cyan">Attiva</Chip> : <Chip>Disattivata</Chip>}</td>
                    <td className="td text-right">{isSystemPractice(p.name) ? <span className="text-sm text-muted">—</span> : <Button size="sm" variant="secondary" onClick={() => setEditing(p)}>Modifica<span className="sr-only"> {p.name}</span></Button>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </ScrollArea>
        </>
      )}
      <PracticeForm editing={editing} onClose={() => setEditing(null)} onSaved={(m) => { setEditing(null); setNotice(m); for (const k of ["admin-practices", "practices-lookup", "admin-employees"]) void qc.invalidateQueries({ queryKey: [k] }); }} />
    </div>
  );
}

function PracticeForm({ editing, onClose, onSaved }: { editing: Practice | "new" | null; onClose: () => void; onSaved: (m: string) => void }) {
  const isNew = editing === "new";
  const practice = editing && editing !== "new" ? editing : null;
  const [v, setV] = useState({ name: "", active: true });
  const [seen, setSeen] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<{ message: string; issues: string[] } | null>(null);
  if (editing !== seen) {
    setSeen(editing); setError(null);
    setV(practice ? { name: practice.name, active: practice.is_active } : { name: "", active: true });
  }
  async function submit(e: FormEvent) {
    e.preventDefault(); setBusy(true); setError(null);
    const name = v.name.trim();
    try {
      if (isNew) unwrap(await api.POST("/api/v1/practices", { body: { name } }));
      else if (practice) unwrap(await api.PATCH("/api/v1/practices/{practice_id}", { params: { path: { practice_id: practice.id } }, body: { name, is_active: v.active } }));
      onSaved(isNew ? `Practice creata: ${name}.` : `Practice aggiornata: ${name}.`);
    } catch (err) { setError(errorDetails(err)); } finally { setBusy(false); }
  }
  return (
    <Modal open={editing !== null} title={isNew ? "Nuova practice" : `Modifica ${practice?.name ?? ""}`} onClose={onClose}>
      <form onSubmit={submit} className="space-y-4">
        <Problems error={error} />
        <TextField id="pf-name" label="Nome della practice" required maxLength={100} value={v.name} onChange={(e) => setV({ ...v, name: e.target.value })} />
        {!isNew && <CheckField id="pf-active" label="Practice attiva" checked={v.active} onChange={(e) => setV({ ...v, active: e.target.checked })} hint="Disattivata: non si può scegliere per un collaboratore; chi la ha già la mantiene." />}
        <div className="flex justify-end gap-2"><Button type="button" variant="ghost" onClick={onClose}>Annulla</Button><Button type="submit" loading={busy} disabled={!v.name.trim()}>{isNew ? "Crea la practice" : "Salva"}</Button></div>
      </form>
    </Modal>
  );
}
