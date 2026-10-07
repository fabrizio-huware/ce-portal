import { keepPreviousData, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";

import { api, unwrap } from "../../api/client";
import type { components } from "../../api/schema";
import { Problems } from "../../components/ActionsBar";
import { AdminHeader, AdminOnly } from "../../components/admin/AdminHeader";
import { Chip } from "../../components/ui/Badge";
import { Button } from "../../components/ui/Button";
import { CheckField, SelectField, TextAreaField, TextField } from "../../components/ui/Fields";
import { EmptyState, ErrorBox, Notice } from "../../components/ui/Feedback";
import { Modal } from "../../components/ui/Modal";
import { Pagination } from "../../components/ui/Pagination";
import { ScrollArea } from "../../components/ui/ScrollArea";
import { Spinner } from "../../components/ui/Spinner";
import { useTextParam, useUrlFilters } from "../../hooks/useUrlFilters";
import { errorDetails, errorMessage } from "../../lib/errors";

type Client = components["schemas"]["ClientOut"];
const LIMIT = 50;

export function ClientsPage() {
  return <AdminOnly><Clients /></AdminOnly>;
}

function Clients() {
  const f = useUrlFilters();
  const [q, setQ] = useTextParam(f, "q");
  const [editing, setEditing] = useState<Client | "new" | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const active = f.get("stato");
  const query = { ...(f.get("q") && { q: f.get("q") }), ...(active && { is_active: active === "1" }), limit: LIMIT, offset: (f.page - 1) * LIMIT };
  const list = useQuery({ queryKey: ["admin-clients", query], placeholderData: keepPreviousData, queryFn: async () => unwrap(await api.GET("/api/v1/clients", { params: { query } })) });
  const qc = useQueryClient();
  return (
    <div>
      <AdminHeader subtitle="I clienti dei conti economici. Un cliente non si elimina: si disattiva, così non compare più nelle scelte ma i CE esistenti restano." actions={<Button variant="accent" onClick={() => setEditing("new")}>+ Nuovo cliente</Button>} />
      <section aria-label="Filtri" className="card mb-6 grid gap-4 p-4 sm:grid-cols-2">
        <TextField id="c-q" label="Cerca per nome" value={q} onChange={(e) => setQ(e.target.value)} />
        <SelectField id="c-active" label="Stato" value={active} onChange={(e) => f.set({ stato: e.target.value || null })}><option value="">Tutti</option><option value="1">Attivi</option><option value="0">Disattivati</option></SelectField>
      </section>
      {notice && <div className="mb-4"><Notice tone="ok">{notice}</Notice></div>}
      {list.isPending ? <div className="py-12 text-center"><Spinner label="Caricamento dei clienti…" /></div>
        : list.isError ? <ErrorBox message={errorMessage(list.error)} onRetry={() => list.refetch()} />
        : list.data.items.length === 0 ? <EmptyState title="Nessun cliente">Cambia i filtri o aggiungi un cliente.</EmptyState> : (
        <>
          <p aria-live="polite" className="mb-3 text-sm text-muted"><strong className="text-ink">{list.data.total}</strong> {list.data.total === 1 ? "cliente" : "clienti"}</p>
          <ScrollArea label="Elenco dei clienti" className="card">
            <table className="w-full min-w-[40rem] border-collapse">
              <thead className="border-b border-line bg-surface/60"><tr><th className="th">Nome</th><th className="th">Indirizzo</th><th className="th">Riferimento esterno</th><th className="th">Stato</th><th className="th"><span className="sr-only">Azioni</span></th></tr></thead>
              <tbody className="divide-y divide-line">
                {list.data.items.map((c) => (
                  <tr key={c.id}><td className="td font-medium">{c.name}</td><td className="td text-muted">{c.address ?? "—"}</td><td className="td">{c.external_ref ?? "—"}</td>
                    <td className="td">{c.is_active ? <Chip tone="cyan">Attivo</Chip> : <Chip>Disattivato</Chip>}</td>
                    <td className="td text-right"><Button size="sm" variant="secondary" onClick={() => setEditing(c)}>Modifica<span className="sr-only"> {c.name}</span></Button></td></tr>
                ))}
              </tbody>
            </table>
          </ScrollArea>
          <Pagination total={list.data.total} limit={LIMIT} offset={(f.page - 1) * LIMIT} onChange={(o) => f.set({ page: String(o / LIMIT + 1) }, true)} />
        </>
      )}
      <ClientForm editing={editing} onClose={() => setEditing(null)} onSaved={(m) => { setEditing(null); setNotice(m); for (const k of ["admin-clients", "clients-lookup"]) void qc.invalidateQueries({ queryKey: [k] }); }} />
    </div>
  );
}

function ClientForm({ editing, onClose, onSaved }: { editing: Client | "new" | null; onClose: () => void; onSaved: (m: string) => void }) {
  const isNew = editing === "new";
  const client = editing && editing !== "new" ? editing : null;
  const [v, setV] = useState({ name: "", address: "", ref: "", active: true });
  const [seen, setSeen] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<{ message: string; issues: string[] } | null>(null);
  if (editing !== seen) {
    setSeen(editing); setError(null);
    setV(client ? { name: client.name, address: client.address ?? "", ref: client.external_ref ?? "", active: client.is_active } : { name: "", address: "", ref: "", active: true });
  }
  async function submit(e: FormEvent) {
    e.preventDefault(); setBusy(true); setError(null);
    const body = { name: v.name.trim(), address: v.address.trim() || null, external_ref: v.ref.trim() || null };
    try {
      if (isNew) unwrap(await api.POST("/api/v1/clients", { body }));
      else if (client) unwrap(await api.PATCH("/api/v1/clients/{client_id}", { params: { path: { client_id: client.id } }, body: { ...body, is_active: v.active } }));
      onSaved(isNew ? `Cliente creato: ${body.name}.` : `Cliente aggiornato: ${body.name}.`);
    } catch (err) { setError(errorDetails(err)); } finally { setBusy(false); }
  }
  return (
    <Modal open={editing !== null} title={isNew ? "Nuovo cliente" : `Modifica ${client?.name ?? ""}`} onClose={onClose}>
      <form onSubmit={submit} className="space-y-4">
        <Problems error={error} />
        <TextField id="cf-name" label="Nome del cliente" required maxLength={300} value={v.name} onChange={(e) => setV({ ...v, name: e.target.value })} />
        <TextAreaField id="cf-address" label="Indirizzo (facoltativo)" value={v.address} onChange={(e) => setV({ ...v, address: e.target.value })} />
        <TextField id="cf-ref" label="Riferimento esterno (facoltativo)" maxLength={100} value={v.ref} onChange={(e) => setV({ ...v, ref: e.target.value })} hint="Per esempio il codice cliente in NetSuite." />
        {!isNew && <CheckField id="cf-active" label="Cliente attivo" checked={v.active} onChange={(e) => setV({ ...v, active: e.target.checked })} hint="Disattivato: non si può scegliere nei nuovi CE." />}
        <div className="flex justify-end gap-2"><Button type="button" variant="ghost" onClick={onClose}>Annulla</Button><Button type="submit" loading={busy} disabled={!v.name.trim()}>{isNew ? "Crea il cliente" : "Salva"}</Button></div>
      </form>
    </Modal>
  );
}
