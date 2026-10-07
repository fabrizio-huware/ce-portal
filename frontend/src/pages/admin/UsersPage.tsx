import { keepPreviousData, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";

import { api, unwrap } from "../../api/client";
import type { components } from "../../api/schema";
import { Problems } from "../../components/ActionsBar";
import { AdminHeader, AdminOnly } from "../../components/admin/AdminHeader";
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
import { datetime } from "../../lib/format";
import { ROLE_LABEL } from "../../lib/status";

type User = components["schemas"]["UserOut"];
type Role = "admin" | "presale" | "viewer";
const LIMIT = 50;

export function UsersPage() {
  return <AdminOnly><Users /></AdminOnly>;
}

function Users() {
  const f = useUrlFilters();
  const [q, setQ] = useTextParam(f, "q");
  const [editing, setEditing] = useState<User | "new" | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const role = f.get("ruolo") as Role | "";
  const active = f.get("stato");
  const query = { ...(f.get("q") && { q: f.get("q") }), ...(role && { role }), ...(active && { is_active: active === "1" }), limit: LIMIT, offset: (f.page - 1) * LIMIT };
  const list = useQuery({ queryKey: ["admin-users", query], placeholderData: keepPreviousData, queryFn: async () => unwrap(await api.GET("/api/v1/users", { params: { query } })) });
  const qc = useQueryClient();

  return (
    <div>
      <AdminHeader subtitle="Chi può accedere al portale e con quale ruolo. Gli utenti si abilitano qui: chi non è in elenco non può entrare." actions={<Button variant="accent" onClick={() => setEditing("new")}>+ Nuovo utente</Button>} />
      <section aria-label="Filtri" className="card mb-6 grid gap-4 p-4 sm:grid-cols-3">
        <TextField id="u-q" label="Cerca per nome o email" value={q} onChange={(e) => setQ(e.target.value)} />
        <SelectField id="u-role" label="Ruolo" value={role} onChange={(e) => f.set({ ruolo: e.target.value || null })}><option value="">Tutti</option>{(["admin", "presale", "viewer"] as const).map((r) => <option key={r} value={r}>{ROLE_LABEL[r]}</option>)}</SelectField>
        <SelectField id="u-active" label="Stato" value={active} onChange={(e) => f.set({ stato: e.target.value || null })}><option value="">Tutti</option><option value="1">Attivi</option><option value="0">Disattivati</option></SelectField>
      </section>
      {notice && <div className="mb-4"><Notice tone="ok">{notice}</Notice></div>}
      {list.isPending ? <div className="py-12 text-center"><Spinner label="Caricamento degli utenti…" /></div>
        : list.isError ? <ErrorBox message={errorMessage(list.error)} onRetry={() => list.refetch()} />
        : list.data.items.length === 0 ? <EmptyState title="Nessun utente">Cambia i filtri o aggiungi un utente.</EmptyState> : (
        <>
          <p aria-live="polite" className="mb-3 text-sm text-muted"><strong className="text-ink">{list.data.total}</strong> {list.data.total === 1 ? "utente" : "utenti"}</p>
          <ScrollArea label="Elenco degli utenti" className="card">
            <table className="w-full min-w-[46rem] border-collapse">
              <thead className="border-b border-line bg-surface/60"><tr><th className="th">Nome</th><th className="th">Email</th><th className="th">Ruolo</th><th className="th">Stato</th><th className="th">Ultimo accesso</th><th className="th"><span className="sr-only">Azioni</span></th></tr></thead>
              <tbody className="divide-y divide-line">
                {list.data.items.map((u) => (
                  <tr key={u.id}>
                    <td className="td font-medium">{u.full_name}</td><td className="td">{u.email}</td><td className="td">{ROLE_LABEL[u.role]}</td>
                    <td className="td">{u.is_active ? <Chip tone="cyan">Attivo</Chip> : <Chip>Disattivato</Chip>}</td>
                    <td className="td whitespace-nowrap text-muted tnum">{u.last_login_at ? datetime(u.last_login_at) : "Mai"}</td>
                    <td className="td text-right"><Button size="sm" variant="secondary" onClick={() => setEditing(u)}>Modifica<span className="sr-only"> {u.full_name}</span></Button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </ScrollArea>
          <Pagination total={list.data.total} limit={LIMIT} offset={(f.page - 1) * LIMIT} onChange={(o) => f.set({ page: String(o / LIMIT + 1) }, true)} />
        </>
      )}
      <UserForm editing={editing} onClose={() => setEditing(null)} onSaved={(msg) => { setEditing(null); setNotice(msg); void qc.invalidateQueries({ queryKey: ["admin-users"] }); }} />
    </div>
  );
}

function UserForm({ editing, onClose, onSaved }: { editing: User | "new" | null; onClose: () => void; onSaved: (message: string) => void }) {
  const isNew = editing === "new";
  const user = editing && editing !== "new" ? editing : null;
  const [v, setV] = useState({ email: "", name: "", role: "presale" as Role, active: true });
  const [seen, setSeen] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<{ message: string; issues: string[] } | null>(null);
  if (editing !== seen) { // ricarica il modulo quando si apre su un utente diverso
    setSeen(editing);
    setError(null);
    setV(user ? { email: user.email, name: user.full_name, role: user.role as Role, active: user.is_active } : { email: "", name: "", role: "presale", active: true });
  }
  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true); setError(null);
    try {
      if (isNew) {
        const created = unwrap(await api.POST("/api/v1/users", { body: { email: v.email.trim(), full_name: v.name.trim(), role: v.role } }));
        onSaved(`Utente creato: ${created.full_name}. Riceve una email con il link per accedere.`);
      } else if (user) {
        unwrap(await api.PATCH("/api/v1/users/{user_id}", { params: { path: { user_id: user.id } }, body: { full_name: v.name.trim(), role: v.role, is_active: v.active } }));
        onSaved(`Utente aggiornato: ${v.name.trim()}.`);
      }
    } catch (err) { setError(errorDetails(err)); } finally { setBusy(false); }
  }
  return (
    <Modal open={editing !== null} title={isNew ? "Nuovo utente" : `Modifica ${user?.full_name ?? ""}`} onClose={onClose}>
      <form onSubmit={submit} className="space-y-4">
        <Problems error={error} />
        {isNew ? <TextField id="uf-email" label="Email aziendale" type="email" required value={v.email} onChange={(e) => setV({ ...v, email: e.target.value })} hint="Deve essere un indirizzo del dominio autorizzato: serve per l'accesso con Google." />
          : <p className="text-muted">{user?.email}</p>}
        <TextField id="uf-name" label="Nome e cognome" required maxLength={200} value={v.name} onChange={(e) => setV({ ...v, name: e.target.value })} />
        <SelectField id="uf-role" label="Ruolo" value={v.role} onChange={(e) => setV({ ...v, role: e.target.value as Role })} hint="Admin: tutto, compresa l'approvazione. Presale: crea e modifica i propri CE. Viewer: vede solo i CE approvati, senza costi.">
          {(["admin", "presale", "viewer"] as const).map((r) => <option key={r} value={r}>{ROLE_LABEL[r]}</option>)}
        </SelectField>
        {!isNew && <CheckField id="uf-active" label="Può accedere al portale" checked={v.active} onChange={(e) => setV({ ...v, active: e.target.checked })} hint="Disattivando un utente perde subito l'accesso; i suoi CE restano." />}
        <div className="flex justify-end gap-2"><Button type="button" variant="ghost" onClick={onClose}>Annulla</Button><Button type="submit" loading={busy} disabled={!v.name.trim() || (isNew && !v.email.trim())}>{isNew ? "Crea l'utente" : "Salva"}</Button></div>
      </form>
    </Modal>
  );
}
