import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";

import { api, unwrap } from "../../api/client";
import { Problems } from "../../components/ActionsBar";
import { AdminHeader, AdminOnly } from "../../components/admin/AdminHeader";
import { StatusBadge } from "../../components/ui/Badge";
import { Button } from "../../components/ui/Button";
import { EmptyState, ErrorBox, Notice } from "../../components/ui/Feedback";
import { Modal } from "../../components/ui/Modal";
import { ScrollArea } from "../../components/ui/ScrollArea";
import { Spinner } from "../../components/ui/Spinner";
import { errorDetails, errorMessage } from "../../lib/errors";
import { datetime, money, period } from "../../lib/format";

export function DeletedPage() {
  return <AdminOnly><Deleted /></AdminOnly>;
}

function Deleted() {
  const qc = useQueryClient();
  const list = useQuery({ queryKey: ["admin-deleted"], queryFn: async () => unwrap(await api.GET("/api/v1/ce", { params: { query: { include_deleted: true, limit: 200 } } })) });
  const [restoring, setRestoring] = useState<{ id: string; code: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<{ message: string; issues: string[] } | null>(null);
  const [notice, setNotice] = useState<{ code: string; id: string } | null>(null);
  const deleted = (list.data?.items ?? []).filter((c) => c.deleted);

  async function restore() {
    if (!restoring) return;
    setBusy(true); setError(null);
    try {
      unwrap(await api.POST("/api/v1/ce/{ce_id}/restore", { params: { path: { ce_id: restoring.id } } }));
      setNotice({ code: restoring.code, id: restoring.id }); setRestoring(null);
      for (const k of ["admin-deleted", "ce-list", "dash-portfolio", "dash-resources"]) void qc.invalidateQueries({ queryKey: [k] });
    } catch (e) { setError(errorDetails(e)); } finally { setBusy(false); }
  }
  return (
    <div>
      <AdminHeader subtitle="I conti economici eliminati non compaiono negli elenchi né nelle dashboard, ma non sono persi: da qui si possono ripristinare." />
      {notice && <div className="mb-4"><Notice tone="ok">«{notice.code}» ripristinato. <Link className="font-medium underline" to={`/ce/${notice.id}`}>Apri il CE</Link></Notice></div>}
      {list.isPending ? <div className="py-12 text-center"><Spinner label="Ricerca dei CE eliminati…" /></div>
        : list.isError ? <ErrorBox message={errorMessage(list.error)} onRetry={() => list.refetch()} />
        : deleted.length === 0 ? <EmptyState title="Nessun CE eliminato">Quando un amministratore ne elimina uno, comparirà qui.</EmptyState> : (
        <>
          <p aria-live="polite" className="mb-3 text-sm text-muted"><strong className="text-ink">{deleted.length}</strong> {deleted.length === 1 ? "CE eliminato" : "CE eliminati"}{list.data.total > list.data.items.length && " (mostrati i più recenti)"}</p>
          <ScrollArea label="CE eliminati" className="card">
            <table className="w-full min-w-[50rem] border-collapse">
              <thead className="border-b border-line bg-surface/60"><tr><th className="th">Codice</th><th className="th">Cliente</th><th className="th">Progetto</th><th className="th">Periodo</th><th className="th">Stato</th><th className="th text-right">Prezzo</th><th className="th">Ultima modifica</th><th className="th"><span className="sr-only">Azioni</span></th></tr></thead>
              <tbody className="divide-y divide-line">
                {deleted.map((c) => (
                  <tr key={c.ce_id}><td className="td whitespace-nowrap font-medium">{c.code}</td><td className="td">{c.client.name}</td><td className="td">{c.project_name}</td>
                    <td className="td whitespace-nowrap text-muted tnum">{period(c.start_date, c.end_date)}</td><td className="td"><StatusBadge status={c.status} /></td>
                    <td className="td whitespace-nowrap text-right tnum">{money(c.price)}</td><td className="td whitespace-nowrap text-muted tnum">{datetime(c.updated_at)}</td>
                    <td className="td text-right"><Button size="sm" variant="secondary" onClick={() => setRestoring({ id: c.ce_id, code: c.code })}>Ripristina<span className="sr-only"> {c.code}</span></Button></td></tr>
                ))}
              </tbody>
            </table>
          </ScrollArea>
        </>
      )}
      <Modal open={restoring !== null} title="Ripristina il CE" onClose={() => { setRestoring(null); setError(null); }}
        footer={<><Button variant="ghost" onClick={() => { setRestoring(null); setError(null); }}>Annulla</Button><Button loading={busy} onClick={() => void restore()}>Ripristina</Button></>}>
        <p>Ripristinare «{restoring?.code}»? Tornerà negli elenchi, nelle dashboard e nelle esportazioni, nello stato in cui era.</p>
        <Problems error={error} />
      </Modal>
    </div>
  );
}
