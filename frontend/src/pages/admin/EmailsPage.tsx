import { keepPreviousData, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { api, unwrap } from "../../api/client";
import { AdminHeader, AdminOnly } from "../../components/admin/AdminHeader";
import { Chip } from "../../components/ui/Badge";
import { Button } from "../../components/ui/Button";
import { SelectField, TextField } from "../../components/ui/Fields";
import { EmptyState, ErrorBox, Notice } from "../../components/ui/Feedback";
import { Pagination } from "../../components/ui/Pagination";
import { ScrollArea } from "../../components/ui/ScrollArea";
import { Spinner } from "../../components/ui/Spinner";
import { useTextParam, useUrlFilters } from "../../hooks/useUrlFilters";
import { errorMessage } from "../../lib/errors";
import { datetime } from "../../lib/format";

const LIMIT = 50;
type Status = "pending" | "sent" | "failed";
const TYPES: Record<string, string> = {
  ce_submitted: "CE inviato in approvazione", ce_approved: "CE approvato", ce_rejected: "CE rifiutato",
  ce_new_version: "Nuova versione", user_enabled: "Accesso al portale", test: "Email di prova",
};
const STATUS: Record<Status, { label: string; cls: string }> = {
  pending: { label: "In coda", cls: "border-amber-200 bg-amber-50 text-amber-800" },
  sent: { label: "Inviata", cls: "border-emerald-200 bg-emerald-50 text-emerald-800" },
  failed: { label: "Fallita", cls: "border-red-200 bg-red-50 text-red-800" },
};

export function EmailsPage() {
  return <AdminOnly><Emails /></AdminOnly>;
}

function Emails() {
  const qc = useQueryClient();
  const f = useUrlFilters();
  const [recipient, setRecipient] = useTextParam(f, "dest");
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const status = f.get("stato") as Status | "";
  const type = f.get("tipo");
  const query = { ...(status && { status }), ...(type && { type }), ...(f.get("dest") && { recipient: f.get("dest") }), limit: LIMIT, offset: (f.page - 1) * LIMIT };
  const list = useQuery({ queryKey: ["admin-emails", query], placeholderData: keepPreviousData, queryFn: async () => unwrap(await api.GET("/api/v1/notifications", { params: { query } })) });
  const refresh = () => void qc.invalidateQueries({ queryKey: ["admin-emails"] });

  async function act(name: string, fn: () => Promise<string>) {
    setBusy(name); setError(null); setNotice(null);
    try { setNotice(await fn()); refresh(); } catch (e) { setError(errorMessage(e)); } finally { setBusy(null); }
  }
  const dispatch = () => act("dispatch", async () => {
    const r = unwrap(await api.POST("/api/v1/notifications/dispatch"));
    return r.processed === 0 ? "Nessuna email da inviare in questo momento." : `Elaborate ${r.processed}: inviate ${r.sent}, rimandate ${r.deferred}, fallite ${r.failed}. Ancora in coda: ${r.remaining}.`;
  });
  const test = () => act("test", async () => {
    const r = unwrap(await api.POST("/api/v1/notifications/test"));
    if (r.status === "sent") return `Email di prova inviata a ${r.recipient}.`;
    throw new Error(`Email di prova non inviata (${STATUS[r.status as Status]?.label ?? r.status})${r.error ? `: ${r.error}` : ""}`);
  });
  const retry = (id: string, to: string) => act(id, async () => {
    const r = unwrap(await api.POST("/api/v1/notifications/{notification_id}/retry", { params: { path: { notification_id: id } } }));
    if (r.status === "failed") throw new Error(`Nuovo tentativo non riuscito per ${to}${r.error ? `: ${r.error}` : ""}`);
    return `Nuovo tentativo per ${to}: ${STATUS[r.status as Status]?.label.toLowerCase() ?? r.status}.`;
  });

  return (
    <div>
      <AdminHeader subtitle="Le email che il portale invia (invio in approvazione, approvazione, rifiuto, nuove versioni, nuovi utenti). Qui si vede se sono partite e perché no." actions={<>
        <Button variant="secondary" loading={busy === "dispatch"} onClick={() => void dispatch()}>Invia subito quelle in coda</Button>
        <Button variant="accent" loading={busy === "test"} onClick={() => void test()}>Invia un'email di prova a me</Button></>} />
      <section aria-label="Filtri" className="card mb-6 grid gap-4 p-4 sm:grid-cols-3">
        <SelectField id="m-status" label="Stato" value={status} onChange={(e) => f.set({ stato: e.target.value || null })}><option value="">Tutti</option>{(Object.keys(STATUS) as Status[]).map((s) => <option key={s} value={s}>{STATUS[s].label}</option>)}</SelectField>
        <SelectField id="m-type" label="Tipo" value={type} onChange={(e) => f.set({ tipo: e.target.value || null })}><option value="">Tutti</option>{Object.entries(TYPES).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</SelectField>
        <TextField id="m-rcpt" label="Destinatario" value={recipient} onChange={(e) => setRecipient(e.target.value)} placeholder="parte dell'indirizzo" />
      </section>
      {notice && <div className="mb-4"><Notice tone="ok">{notice}</Notice></div>}
      {error && <div className="mb-4"><ErrorBox message={error} /></div>}
      {list.isPending ? <div className="py-12 text-center"><Spinner label="Caricamento delle email…" /></div>
        : list.isError ? <ErrorBox message={errorMessage(list.error)} onRetry={() => list.refetch()} />
        : list.data.items.length === 0 ? <EmptyState title="Nessuna email">Compariranno qui quando il portale ne invierà.</EmptyState> : (
        <>
          <p aria-live="polite" className="mb-3 text-sm text-muted"><strong className="text-ink">{list.data.total}</strong> {list.data.total === 1 ? "email" : "email"}</p>
          <ScrollArea label="Elenco delle email" className="card">
            <table className="w-full min-w-[56rem] border-collapse">
              <thead className="border-b border-line bg-surface/60"><tr><th className="th">Creata</th><th className="th">Destinatario</th><th className="th">Oggetto</th><th className="th">Stato</th><th className="th text-right">Tentativi</th><th className="th">Dettaglio</th><th className="th"><span className="sr-only">Azioni</span></th></tr></thead>
              <tbody className="divide-y divide-line">
                {list.data.items.map((m) => {
                  const s = STATUS[m.status as Status];
                  return (
                    <tr key={m.id}>
                      <td className="td whitespace-nowrap text-muted tnum">{datetime(m.created_at)}</td><td className="td">{m.recipient}</td>
                      <td className="td"><span className="block">{m.subject ?? "—"}</span><Chip>{TYPES[m.type] ?? m.type}</Chip></td>
                      <td className="td"><span className={`inline-flex whitespace-nowrap rounded-full border px-2.5 py-0.5 text-xs font-medium ${s.cls}`}>{s.label}</span></td>
                      <td className="td text-right tnum">{m.attempts}</td>
                      <td className="td max-w-xs text-sm">{m.error ? <span className="text-red-800">{m.error}</span> : m.status === "pending" ? <span className="text-muted">Prossimo tentativo: {datetime(m.next_attempt_at)}</span> : m.sent_at ? <span className="text-muted">Inviata il {datetime(m.sent_at)}</span> : "—"}</td>
                      <td className="td text-right">{m.status === "failed" && <Button size="sm" variant="secondary" loading={busy === m.id} onClick={() => void retry(m.id, m.recipient)}>Riprova<span className="sr-only"> per {m.recipient}</span></Button>}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </ScrollArea>
          <Pagination total={list.data.total} limit={LIMIT} offset={(f.page - 1) * LIMIT} onChange={(o) => f.set({ page: String(o / LIMIT + 1) }, true)} />
        </>
      )}
    </div>
  );
}
