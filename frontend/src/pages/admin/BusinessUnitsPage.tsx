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
import { isSystemBusinessUnit, visibilityWarnings } from "../../lib/businessUnits";
import { errorDetails, errorMessage } from "../../lib/errors";

type Unit = components["schemas"]["BusinessUnitOut"];
type ApplyResult = components["schemas"]["ApplyToCEsResult"];

export function BusinessUnitsPage() {
  return <AdminOnly><BusinessUnits /></AdminOnly>;
}

function BusinessUnits() {
  const [editing, setEditing] = useState<Unit | "new" | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [applying, setApplying] = useState(false);
  const list = useQuery({ queryKey: ["admin-business-units"], queryFn: async () => unwrap(await api.GET("/api/v1/business-units")) });
  const qc = useQueryClient();
  return (
    <div>
      <AdminHeader subtitle="Le business unit stanno sopra le practice: ogni practice ne ha una, ogni presale o responsabile ne ha una, e decidono chi vede un CE. Non si eliminano: si disattivano." actions={<div className="flex flex-wrap gap-2"><Button variant="secondary" onClick={() => setApplying(true)}>Assegna ai CE esistenti</Button><Button variant="accent" onClick={() => setEditing("new")}>+ Nuova business unit</Button></div>} />
      {notice && <div className="mb-4"><Notice tone="ok">{notice}</Notice></div>}
      <VisibilityCard onChanged={setNotice} />
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
      <ApplyToCEs open={applying} onClose={() => setApplying(false)} onDone={(m) => { setApplying(false); setNotice(m); void qc.invalidateQueries({ queryKey: ["ce-list"] }); }} />
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

function ApplyToCEs({ open, onClose, onDone }: { open: boolean; onClose: () => void; onDone: (message: string) => void }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<{ message: string; issues: string[] } | null>(null);
  const [result, setResult] = useState<ApplyResult | null>(null);
  async function run() {
    setBusy(true); setError(null);
    try { setResult(unwrap(await api.POST("/api/v1/business-units/apply-to-existing-ces"))); } catch (err) { setError(errorDetails(err)); } finally { setBusy(false); }
  }
  function close() { const r = result; setResult(null); setError(null); if (r) onDone(`Business unit assegnate a ${r.updated} CE; ${r.without_business_units.length} restano senza.`); else onClose(); }
  return (
    <Modal open={open} title="Assegna le business unit ai CE esistenti" onClose={close}>
      <div className="space-y-4">
        <Problems error={error} />
        {!result ? (
          <>
            <p>Per ogni CE che non ha ancora business unit le ricavo dal testo libero che aveva e dalle practice dei collaboratori delle righe. I CE che ne hanno già non si toccano e «Da assegnare» non si assegna mai. Si può ripetere senza danni.</p>
            <p className="text-sm text-muted">Conviene farlo dopo aver creato le business unit e assegnato le practice.</p>
            <div className="flex justify-end gap-2"><Button type="button" variant="ghost" onClick={close}>Annulla</Button><Button type="button" loading={busy} onClick={() => void run()}>Assegna ora</Button></div>
          </>
        ) : (
          <>
            <Notice tone="ok">Business unit assegnate a <strong>{result.updated}</strong> CE.</Notice>
            {result.without_business_units.length > 0 ? (
              <div>
                <p className="font-medium">{result.without_business_units.length} CE restano senza business unit (li vedono solo l'autore e gli amministratori):</p>
                <ul className="mt-1 max-h-48 list-disc overflow-auto pl-5 text-sm">{result.without_business_units.map((c) => <li key={c.ce_id}>{c.code}</li>)}</ul>
                <p className="mt-2 text-sm text-muted">Aprili e scegli le business unit dal dettaglio o dall'editor.</p>
              </div>
            ) : <p>Tutti i CE hanno ora almeno una business unit.</p>}
            <div className="flex justify-end"><Button type="button" onClick={close}>Chiudi</Button></div>
          </>
        )}
      </div>
    </Modal>
  );
}

function VisibilityCard({ onChanged }: { onChanged: (message: string) => void }) {
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["business-units-visibility"], queryFn: async () => unwrap(await api.GET("/api/v1/business-units/visibility")) });
  const [confirm, setConfirm] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<{ message: string; issues: string[] } | null>(null);
  const warnings = q.data ? visibilityWarnings(q.data.report) : [];
  async function put(enabled: boolean) {
    setBusy(true); setError(null);
    try {
      unwrap(await api.PUT("/api/v1/business-units/visibility", { body: { enabled } }));
      await qc.invalidateQueries({ queryKey: ["business-units-visibility"] });
      void qc.invalidateQueries({ queryKey: ["ce-list"] });
      setConfirm(false);
      onChanged(enabled ? "Visibilità per business unit accesa." : "Visibilità per business unit spenta: tutti vedono tutto, come prima.");
    } catch (err) { setError(errorDetails(err)); } finally { setBusy(false); }
  }
  function toggle() {
    if (!q.data || busy) return;
    if (q.data.enabled) void put(false);
    else if (warnings.length > 0) setConfirm(true);
    else void put(true);
  }
  if (q.isPending) return null;
  if (q.isError) return <div className="mb-4"><ErrorBox message={errorMessage(q.error)} onRetry={() => q.refetch()} /></div>;
  const on = q.data.enabled;
  return (
    <section aria-label="Visibilità per business unit" className="card mb-5 space-y-3 p-4 sm:p-5">
      <Problems error={confirm ? null : error} />
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-lg font-medium">Visibilità per business unit</h2>
          <p className="mt-1 text-sm text-muted" data-testid="visibility-state">
            {on ? "Accesa: un presale o un responsabile vede i CE che coinvolgono la sua business unit e quelli che ha creato, per intero; gli amministratori vedono tutto. Gli altri CE per lui non esistono."
              : "Spenta: tutti i presale vedono tutti i CE, come prima. Accendila quando le business unit sono pronte."}
          </p>
        </div>
        <button type="button" role="switch" aria-checked={on} aria-label="Visibilità per business unit" disabled={busy} onClick={toggle}
          className={`relative inline-flex h-7 w-12 shrink-0 items-center rounded-full border transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal-600 ${on ? "border-ink bg-ink" : "border-line bg-surface"} ${busy ? "opacity-60" : ""}`}>
          <span aria-hidden className={`inline-block h-5 w-5 rounded-full transition-transform ${on ? "translate-x-6 bg-white" : "translate-x-1 bg-muted"}`} />
        </button>
      </div>
      {warnings.length > 0 ? (
        <div className="rounded-xl border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-900">
          <p className="font-medium">{on ? "Da sistemare:" : "Prima di accenderla:"}</p>
          <ul className="mt-1 list-disc space-y-1 pl-5">{warnings.map((w) => <li key={w}>{w}</li>)}</ul>
          {q.data.report.ces_without_business_units > 0 && <p className="mt-2">Per i CE vecchi usa «Assegna ai CE esistenti» qui sotto.</p>}
        </div>
      ) : <p className="text-sm text-muted">Tutto pronto: ogni CE e ogni presale ha la sua business unit.</p>}
      <Modal open={confirm} title="Accendere la visibilità per business unit?" onClose={() => setConfirm(false)}>
        <div className="space-y-4">
          <Problems error={error} />
          <p>Da subito un presale o un responsabile vedrà solo i CE della sua business unit e quelli che ha creato. Ti segnalo che:</p>
          <ul className="list-disc space-y-1 pl-5 text-sm">{warnings.map((w) => <li key={w}>{w}</li>)}</ul>
          <p className="text-sm text-muted">Si può spegnere in qualunque momento: tutti tornano a vedere tutto.</p>
          <div className="flex justify-end gap-2"><Button type="button" variant="ghost" onClick={() => setConfirm(false)}>Annulla</Button><Button type="button" loading={busy} onClick={() => void put(true)}>Accendi comunque</Button></div>
        </div>
      </Modal>
    </section>
  );
}
