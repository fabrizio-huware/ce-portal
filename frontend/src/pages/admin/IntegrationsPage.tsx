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
import { datetime } from "../../lib/format";
import { errorDetails, errorMessage } from "../../lib/errors";
import { isServiceAccountEmail, PERMISSIONS, permissionLabels, portalAudience, togglePermission } from "../../lib/integrations";

type Integration = components["schemas"]["IntegrationOut"];

export function IntegrationsPage() {
  return <AdminOnly><Integrations /></AdminOnly>;
}

function Integrations() {
  const [editing, setEditing] = useState<Integration | "new" | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const list = useQuery({ queryKey: ["admin-integrations"], queryFn: async () => unwrap(await api.GET("/api/v1/integrations")) });
  const qc = useQueryClient();
  return (
    <div>
      <AdminHeader subtitle="Programmi esterni autorizzati ad agire con un account di servizio Google. Un'integrazione disattivata smette di funzionare alla richiesta successiva." actions={<Button variant="accent" onClick={() => setEditing("new")}>+ Nuova integrazione</Button>} />
      {notice && <div className="mb-4"><Notice tone="ok">{notice}</Notice></div>}
      <p className="mb-4 rounded-lg bg-cyan-100 px-4 py-2.5 text-sm">Indirizzo da usare come audience del token: <code className="font-mono text-xs">{portalAudience(window.location.origin)}</code></p>
      {list.isPending ? <div className="py-12 text-center"><Spinner label="Caricamento delle integrazioni…" /></div>
        : list.isError ? <ErrorBox message={errorMessage(list.error)} onRetry={() => list.refetch()} />
        : list.data.length === 0 ? <EmptyState title="Nessuna integrazione">Registra l'account di servizio di un programma esterno con «Nuova integrazione».</EmptyState> : (
        <>
          <p aria-live="polite" className="mb-3 text-sm text-muted"><strong className="text-ink">{list.data.length}</strong> {list.data.length === 1 ? "integrazione" : "integrazioni"}</p>
          <ScrollArea label="Elenco delle integrazioni" className="card">
            <table className="w-full min-w-[52rem] border-collapse">
              <thead className="border-b border-line bg-surface/60"><tr><th className="th">Nome</th><th className="th">Account di servizio</th><th className="th">Permessi</th><th className="th">Ultimo utilizzo</th><th className="th">Stato</th><th className="th"><span className="sr-only">Azioni</span></th></tr></thead>
              <tbody className="divide-y divide-line">
                {list.data.map((i) => (
                  <tr key={i.id}>
                    <td className="td font-medium">{i.name}</td>
                    <td className="td break-all font-mono text-xs text-muted">{i.service_account_email}</td>
                    <td className="td"><span className="flex flex-wrap gap-1">{permissionLabels(i.permissions).map((l) => <Chip key={l}>{l}</Chip>)}</span></td>
                    <td className="td tnum">{i.last_used_at ? datetime(i.last_used_at) : "Mai"}</td>
                    <td className="td">{i.is_active ? <Chip tone="cyan">Attiva</Chip> : <Chip>Disattivata</Chip>}</td>
                    <td className="td text-right"><Button size="sm" variant="secondary" onClick={() => setEditing(i)}>Modifica<span className="sr-only"> {i.name}</span></Button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </ScrollArea>
        </>
      )}
      <IntegrationForm editing={editing} onClose={() => setEditing(null)} onSaved={(m) => { setEditing(null); setNotice(m); void qc.invalidateQueries({ queryKey: ["admin-integrations"] }); }} />
    </div>
  );
}

const ALL = PERMISSIONS.map((p) => p.key) as string[];

function IntegrationForm({ editing, onClose, onSaved }: { editing: Integration | "new" | null; onClose: () => void; onSaved: (m: string) => void }) {
  const isNew = editing === "new";
  const integration = editing && editing !== "new" ? editing : null;
  const [v, setV] = useState({ name: "", email: "", permissions: ALL, active: true });
  const [seen, setSeen] = useState<unknown>(null);
  const [touched, setTouched] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<{ message: string; issues: string[] } | null>(null);
  if (editing !== seen) {
    setSeen(editing); setError(null); setTouched(false);
    setV(integration ? { name: integration.name, email: integration.service_account_email, permissions: integration.permissions, active: integration.is_active } : { name: "", email: "", permissions: ALL, active: true });
  }
  const emailProblem = isNew && touched && v.email.trim() !== "" && !isServiceAccountEmail(v.email) ? "Inserisci l'email di un account di servizio, che finisce con .iam.gserviceaccount.com" : undefined;
  const valid = v.name.trim() !== "" && v.permissions.length > 0 && (!isNew || isServiceAccountEmail(v.email));
  async function submit(e: FormEvent) {
    e.preventDefault(); setBusy(true); setError(null);
    const name = v.name.trim();
    try {
      if (isNew) unwrap(await api.POST("/api/v1/integrations", { body: { name, service_account_email: v.email.trim().toLowerCase(), permissions: v.permissions as PermissionList } }));
      else if (integration) unwrap(await api.PATCH("/api/v1/integrations/{integration_id}", { params: { path: { integration_id: integration.id } }, body: { name, permissions: v.permissions as PermissionList, is_active: v.active } }));
      onSaved(isNew ? `Integrazione registrata: ${name}.` : `Integrazione aggiornata: ${name}.`);
    } catch (err) { setError(errorDetails(err)); } finally { setBusy(false); }
  }
  return (
    <Modal open={editing !== null} title={isNew ? "Nuova integrazione" : `Modifica ${integration?.name ?? ""}`} onClose={onClose}>
      <form onSubmit={submit} className="space-y-4">
        <Problems error={error} />
        <TextField id="if-name" label="Nome" required maxLength={100} value={v.name} onChange={(e) => setV({ ...v, name: e.target.value })} />
        <TextField id="if-email" label="Email dell'account di servizio" required readOnly={!isNew} value={v.email} onChange={(e) => setV({ ...v, email: e.target.value })} onBlur={() => setTouched(true)} error={emailProblem}
          hint={isNew ? "L'indirizzo che finisce con .iam.gserviceaccount.com, quello che il programma esterno usa per farsi firmare il token." : "L'indirizzo non si cambia: per un altro account se ne registra una nuova integrazione."} />
        <fieldset className="space-y-2">
          <legend className="label">Permessi</legend>
          {PERMISSIONS.map((p) => <CheckField key={p.key} id={`if-perm-${p.key}`} label={p.label} checked={v.permissions.includes(p.key)} onChange={(e) => setV({ ...v, permissions: togglePermission(v.permissions, p.key, e.target.checked) })} />)}
          {v.permissions.length === 0 && <p role="alert" className="text-xs text-red-700">Serve almeno un permesso.</p>}
        </fieldset>
        {!isNew && <CheckField id="if-active" label="Integrazione attiva" checked={v.active} onChange={(e) => setV({ ...v, active: e.target.checked })} hint="Disattivata, smette di funzionare alla richiesta successiva; i suoi CE restano." />}
        <div className="flex justify-end gap-2"><Button type="button" variant="ghost" onClick={onClose}>Annulla</Button><Button type="submit" loading={busy} disabled={!valid}>{isNew ? "Registra l'integrazione" : "Salva"}</Button></div>
      </form>
    </Modal>
  );
}

type PermissionList = components["schemas"]["IntegrationCreate"]["permissions"];
