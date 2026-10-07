import { useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent, type ReactNode } from "react";
import { Link, useNavigate } from "react-router-dom";

import { api, unwrap } from "../api/client";
import type { CeDetail } from "../api/types";
import { ApiError, errorDetails } from "../lib/errors";
import { ClientSelect } from "./ClientSelect";
import { Button } from "./ui/Button";
import { ErrorBox } from "./ui/Feedback";
import { Menu, type MenuItem } from "./ui/Menu";
import { Modal } from "./ui/Modal";

type Kind = "submit" | "withdraw" | "approve" | "reject" | "new_version" | "discard" | "realign" | "duplicate" | "delete";

function ensureOk(result: { error?: unknown; response: Response }): void {
  if (result.error !== undefined || !result.response.ok) throw new ApiError(result.response.status, result.error);
}

/** Azioni del flusso di approvazione, mostrate solo se il server le consente (`detail.actions`). */
export function ActionsBar({ detail }: { detail: CeDetail }) {
  const { actions, ce, version, header } = detail;
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [open, setOpen] = useState<Kind | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<{ message: string; issues: string[] } | null>(null);
  const [reason, setReason] = useState("");
  const [realign, setRealign] = useState({ rates: true, calendar: true });
  const [dup, setDup] = useState({ code: "", project: header.project_name, start: header.start_date, end: header.end_date, client: header.client.id });

  const close = () => { setOpen(null); setError(null); };
  const refresh = () => qc.invalidateQueries();

  async function run(kind: Kind) {
    setBusy(true);
    setError(null);
    const path = { params: { path: { ce_id: ce.id } } };
    try {
      switch (kind) {
        case "submit": unwrap(await api.POST("/api/v1/ce/{ce_id}/submit", path)); break;
        case "withdraw": unwrap(await api.POST("/api/v1/ce/{ce_id}/withdraw", path)); break;
        case "approve": unwrap(await api.POST("/api/v1/ce/{ce_id}/approve", path)); break;
        case "reject": unwrap(await api.POST("/api/v1/ce/{ce_id}/reject", { ...path, body: { reason: reason.trim() } })); break;
        case "realign": unwrap(await api.POST("/api/v1/ce/{ce_id}/realign", { ...path, body: realign })); break;
        case "new_version": {
          unwrap(await api.POST("/api/v1/ce/{ce_id}/versions", path));
          await refresh();
          navigate(`/ce/${ce.id}/modifica`);
          break;
        }
        case "discard": unwrap(await api.DELETE("/api/v1/ce/{ce_id}/open-version", path)); break;
        case "delete": {
          ensureOk(await api.DELETE("/api/v1/ce/{ce_id}", path));
          await refresh();
          navigate("/ce");
          break;
        }
        case "duplicate": {
          const created = unwrap(await api.POST("/api/v1/ce/{ce_id}/duplicate", {
            ...path, body: { code: dup.code.trim(), start_date: dup.start, end_date: dup.end, project_name: dup.project.trim() || null, client_id: dup.client || null },
          }));
          await refresh();
          navigate(`/ce/${created.ce.id}/modifica`);
          break;
        }
      }
      await refresh();
      close();
      setReason("");
    } catch (e) {
      setError(errorDetails(e));
    } finally {
      setBusy(false);
    }
  }

  const confirmFooter = (kind: Kind, label: string, variant: "primary" | "danger" = "primary", disabled = false): ReactNode => (
    <>
      <Button variant="ghost" onClick={close}>Annulla</Button>
      <Button variant={variant} loading={busy} disabled={disabled} onClick={() => run(kind)}>{label}</Button>
    </>
  );

  const more: MenuItem[] = [
    { label: "Duplica come nuovo CE", onSelect: () => setOpen("duplicate") },
    ...(actions.discard_version ? [{ label: "Scarta la versione in lavorazione", onSelect: () => setOpen("discard" as Kind) }] : []),
    ...(actions.realign ? [{ label: "Riallinea tariffe e calendario", onSelect: () => setOpen("realign" as Kind) }] : []),
    ...(actions.delete ? ["separator" as const, { label: "Elimina il CE", onSelect: () => setOpen("delete" as Kind) }] : []),
  ];
  const label = `«${ce.code}» (versione ${version.number})`;

  return (
    <div className="flex flex-wrap items-center gap-2">
      {actions.edit && <Link to={`/ce/${ce.id}/modifica`} className="inline-flex items-center rounded-lg border border-ink bg-paper px-3 py-1.5 text-sm font-medium hover:bg-surface">Modifica</Link>}
      {actions.submit && <Button size="sm" onClick={() => setOpen("submit")}>Invia in approvazione</Button>}
      {actions.withdraw && <Button size="sm" variant="secondary" onClick={() => setOpen("withdraw")}>Ritira</Button>}
      {actions.approve && <Button size="sm" onClick={() => setOpen("approve")}>Approva</Button>}
      {actions.reject && <Button size="sm" variant="secondary" onClick={() => setOpen("reject")}>Rifiuta</Button>}
      {actions.new_version && <Button size="sm" onClick={() => setOpen("new_version")}>Nuova versione</Button>}
      <Menu label="Altre azioni" items={more} />

      <Modal open={open === "submit"} title="Invia in approvazione" onClose={close} footer={confirmFooter("submit", "Invia in approvazione")}>
        <p>Inviare {label} in approvazione? Gli amministratori ricevono una email. Finché è in approvazione non potrai modificarlo, ma puoi ritirarlo.</p>
        <Problems error={error} />
      </Modal>
      <Modal open={open === "withdraw"} title="Ritira dall'approvazione" onClose={close} footer={confirmFooter("withdraw", "Ritira")}>
        <p>Ritirare {label} dall'approvazione? Torna in bozza e potrai modificarlo.</p><Problems error={error} />
      </Modal>
      <Modal open={open === "approve"} title="Approva" onClose={close} footer={confirmFooter("approve", "Approva")}>
        <p>Approvare {label}? Da ora è visibile ai viewer e non si può più modificare: per cambiarlo si crea una nuova versione.</p><Problems error={error} />
      </Modal>
      <Modal open={open === "reject"} title="Rifiuta" onClose={close} footer={confirmFooter("reject", "Rifiuta", "danger", reason.trim() === "")}>
        <label htmlFor="reject-reason" className="label">Motivo del rifiuto (lo riceve l'autore)</label>
        <textarea id="reject-reason" className="field min-h-24" value={reason} onChange={(e) => setReason(e.target.value)} maxLength={1000} autoFocus />
        <Problems error={error} />
      </Modal>
      <Modal open={open === "new_version"} title="Nuova versione" onClose={close} footer={confirmFooter("new_version", "Crea la versione")}>
        <p>Creare la versione {version.number + 1} a partire da {label}? Si copiano righe, tariffe e calendario; la versione approvata resta quella visibile ai viewer finché non approvi la nuova.</p><Problems error={error} />
      </Modal>
      <Modal open={open === "discard"} title="Scarta la versione in lavorazione" onClose={close} footer={confirmFooter("discard", "Scarta la versione", "danger")}>
        <p>Scartare {label}? Le modifiche non approvate andranno perse. L'ultima versione approvata resta com'è.</p><Problems error={error} />
      </Modal>
      <Modal open={open === "realign"} title="Riallinea tariffe e calendario" onClose={close} footer={confirmFooter("realign", "Riallinea", "primary", !realign.rates && !realign.calendar)}>
        <p>Aggiorna questo CE ai valori correnti. I totali possono cambiare.</p>
        <label className="flex items-center gap-2"><input type="checkbox" className="h-4 w-4 accent-ink" checked={realign.rates} onChange={(e) => setRealign({ ...realign, rates: e.target.checked })} /> Tariffe del listino</label>
        <label className="flex items-center gap-2"><input type="checkbox" className="h-4 w-4 accent-ink" checked={realign.calendar} onChange={(e) => setRealign({ ...realign, calendar: e.target.checked })} /> Giorni non lavorativi del calendario generale</label>
        <Problems error={error} />
      </Modal>
      <Modal open={open === "delete"} title="Elimina il CE" onClose={close} footer={confirmFooter("delete", "Elimina", "danger")}>
        <p>Eliminare {label}? Sparisce dagli elenchi; solo un amministratore può ripristinarlo.</p><Problems error={error} />
      </Modal>
      <Modal open={open === "duplicate"} title="Duplica come nuovo CE" onClose={close} wide>
        <form onSubmit={(e: FormEvent) => { e.preventDefault(); void run("duplicate"); }} className="space-y-4">
          <p className="text-muted">Copia struttura e righe, con tariffe e calendario correnti.</p>
          <div className="grid gap-4 sm:grid-cols-2">
            <div><label htmlFor="dup-code" className="label">Codice del nuovo CE</label><input id="dup-code" className="field" value={dup.code} onChange={(e) => setDup({ ...dup, code: e.target.value })} required maxLength={60} /></div>
            <div><label htmlFor="dup-project" className="label">Nome del progetto</label><input id="dup-project" className="field" value={dup.project} onChange={(e) => setDup({ ...dup, project: e.target.value })} maxLength={300} /></div>
            <div><label htmlFor="dup-start" className="label">Inizio</label><input id="dup-start" type="date" className="field" value={dup.start} onChange={(e) => setDup({ ...dup, start: e.target.value })} required /></div>
            <div><label htmlFor="dup-end" className="label">Fine</label><input id="dup-end" type="date" className="field" value={dup.end} onChange={(e) => setDup({ ...dup, end: e.target.value })} required /></div>
            <div className="sm:col-span-2"><label htmlFor="dup-client" className="label">Cliente</label><ClientSelect id="dup-client" value={dup.client} onChange={(client) => setDup({ ...dup, client })} /></div>
          </div>
          <Problems error={error} />
          <div className="flex justify-end gap-2"><Button type="button" variant="ghost" onClick={close}>Annulla</Button><Button type="submit" loading={busy} disabled={!dup.code.trim()}>Crea il duplicato</Button></div>
        </form>
      </Modal>
    </div>
  );
}

/** Errore dell'API con l'elenco completo dei problemi (per esempio perché un CE non è inviabile). */
export function Problems({ error }: { error: { message: string; issues: string[] } | null }) {
  if (!error) return null;
  const extra = error.issues.filter((i) => i !== error.message);
  return (
    <div role="alert" className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-red-900">
      <p className="font-medium">{error.message}</p>
      {extra.length > 0 && <ul className="mt-2 list-disc space-y-1 pl-5">{extra.map((i) => <li key={i}>{i}</li>)}</ul>}
    </div>
  );
}
export { ErrorBox };
