import { keepPreviousData, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { Link, useBlocker, useParams } from "react-router-dom";

import { api, unwrap } from "../api/client";
import { useEmployees, useProfiles } from "../api/lookups";
import type { CeDetail } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { Problems } from "../components/ActionsBar";
import { StatusBadge, Chip } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { ErrorBox, Notice } from "../components/ui/Feedback";
import { Modal } from "../components/ui/Modal";
import { Spinner } from "../components/ui/Spinner";
import { useDebounced } from "../hooks/useDebounced";
import { GeneralForm } from "../editor/GeneralForm";
import * as m from "../editor/model";
import { PhaseCard } from "../editor/PhaseCard";
import { PreviewBar, type PreviewState } from "../editor/PreviewBar";
import { errorDetails, errorMessage } from "../lib/errors";

const queryKey = (id: string) => ["ce-edit", id];

export function CeEditPage() {
  const { id = "" } = useParams();
  const { isEditor } = useAuth();
  const qc = useQueryClient();
  const q = useQuery({
    queryKey: queryKey(id),
    queryFn: async () => unwrap(await api.GET("/api/v1/ce/{ce_id}", { params: { path: { ce_id: id } } })),
    enabled: isEditor,
    refetchOnMount: "always",
    gcTime: 0,
    staleTime: 0,
  });
  const [savedNotice, setSavedNotice] = useState(false);

  if (!isEditor) return <div className="space-y-4"><BackLink to="/ce" label="← Tutti i conti economici" /><ErrorBox message="Non hai i permessi per modificare i conti economici." /></div>;
  if (q.isPending) return <div className="py-20 text-center"><Spinner label="Caricamento dell'editor…" /></div>;
  if (q.isError) return <div className="space-y-4"><BackLink to="/ce" label="← Tutti i conti economici" /><ErrorBox message={errorMessage(q.error)} onRetry={() => q.refetch()} /></div>;
  const detail = q.data;
  if (!detail.actions.edit) {
    const status = detail.version.status;
    const why =
      status === "approved" ? "È approvata: per cambiarla crea una nuova versione dalla pagina di dettaglio."
      : status === "submitted" ? "È in approvazione: per modificarla ritirala dall'approvazione dalla pagina di dettaglio."
      : `La può modificare solo l'autore (${detail.ce.owner.full_name}) o un amministratore.`;
    return (
      <div className="space-y-4">
        <BackLink to={`/ce/${id}`} label="← Torna al dettaglio" />
        <Notice>Questa versione non si può modificare. {why}</Notice>
      </div>
    );
  }
  return (
    <Editor
      key={`${detail.ce.id}:${detail.version.number}:${detail.version.revision}`}
      detail={detail}
      savedNotice={savedNotice}
      onSaved={(saved) => {
        qc.setQueryData(queryKey(id), saved);
        for (const k of ["ce", "ce-list", "ce-versions", "ce-history"]) void qc.invalidateQueries({ queryKey: [k] });
        setSavedNotice(true);
      }}
      onReload={async () => { setSavedNotice(false); await q.refetch(); }}
    />
  );
}

function BackLink({ to, label }: { to: string; label: string }) {
  return <Link to={to} className="inline-flex items-center gap-1 text-sm font-medium text-teal-700 underline-offset-4 hover:underline">{label}</Link>;
}

type EditorProps = { detail: CeDetail; savedNotice: boolean; onSaved: (saved: CeDetail) => void; onReload: () => Promise<void> };

function Editor({ detail, savedNotice, onSaved, onReload }: EditorProps) {
  const id = detail.ce.id;
  const profiles = useProfiles();
  const employees = useEmployees();
  const [draft, setDraft] = useState<m.Draft>(() => m.draftFromDetail(detail));
  const baseline = useMemo(() => m.contentKey(m.draftFromDetail(detail)), [detail]);
  const json = useMemo(() => m.contentKey(draft), [draft]);
  const dirty = json !== baseline;
  const issues = m.localIssues(draft);
  const invalid = useMemo(() => new Set(issues.map((i) => i.id)), [issues]);
  const months = m.monthsBetween(draft.startDate, draft.endDate);

  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<{ message: string; issues: string[] } | null>(null);
  const [conflict, setConflict] = useState(false);
  const [showIssues, setShowIssues] = useState(false);
  const [removing, setRemoving] = useState<string | null>(null);

  const update = (fn: (d: m.Draft) => m.Draft) => setDraft(fn);

  // ---- anteprima dei totali (calcolo del server, con una breve pausa di digitazione)
  const deb = useDebounced(json, 500);
  const preview = useQuery({
    queryKey: ["ce-preview", id, deb],
    enabled: issues.length === 0,
    placeholderData: keepPreviousData,
    retry: false,
    staleTime: Infinity,
    queryFn: async () => unwrap(await api.POST("/api/v1/ce/{ce_id}/calculate", { params: { path: { ce_id: id } }, body: JSON.parse(deb) })),
  });
  const stale = deb !== json;
  const calc = preview.data ?? detail.calculation;
  const state: PreviewState = issues.length > 0 ? "incomplete" : stale || preview.isFetching ? "calculating" : preview.isError ? "error" : "ok";
  const previewIssues = preview.isError && !stale ? errorDetails(preview.error) : null;

  // ---- uscita con modifiche non salvate
  const blocker = useBlocker(({ currentLocation, nextLocation }) => dirty && !saving && currentLocation.pathname !== nextLocation.pathname);
  useEffect(() => {
    if (!dirty) return;
    const warn = (e: BeforeUnloadEvent) => { e.preventDefault(); e.returnValue = ""; };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [dirty]);

  async function save() {
    setSaveError(null);
    setConflict(false);
    if (issues.length > 0) { setShowIssues(true); return; }
    setShowIssues(false);
    setSaving(true);
    try {
      const saved = unwrap(await api.PUT("/api/v1/ce/{ce_id}/content", { params: { path: { ce_id: id } }, body: m.toContent(draft, detail.version.revision) }));
      onSaved(saved);
    } catch (e) {
      const d = errorDetails(e);
      if (d.status === 409 && (d.body as { detail?: { current_revision?: number } } | undefined)?.detail?.current_revision !== undefined) setConflict(true);
      else setSaveError({ message: d.message, issues: d.issues });
    } finally {
      setSaving(false);
    }
  }

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "s") { e.preventDefault(); void save(); }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  const { version, ce } = detail;
  const phaseToRemove = draft.phases.find((p) => p.key === removing);

  return (
    <div className="space-y-6 pb-28">
      <BackLink to={`/ce/${id}`} label="← Torna al dettaglio" />
      <div>
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="break-words text-3xl font-light sm:text-5xl">{ce.code}</h1>
          <StatusBadge status={version.status} /><Chip>v{version.number}</Chip><Chip tone="cyan">In modifica</Chip>
        </div>
        <p className="mt-2 text-sm text-muted">Le modifiche si salvano con il pulsante «Salva» (o Ctrl+S). I totali si aggiornano mentre scrivi.</p>
      </div>

      {version.status === "rejected" && version.rejection_reason && <ErrorBox message={`Rifiutato${version.rejected_by ? ` da ${version.rejected_by.full_name}` : ""}: ${version.rejection_reason}`} />}
      <PreviewBar calc={calc} state={state} />
      {previewIssues && (
        <div role="status" className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
          <p className="font-medium">{previewIssues.message}</p>
          {previewIssues.issues.length > 0 && <ul className="mt-1 list-disc pl-5">{previewIssues.issues.map((i) => <li key={i}>{i}</li>)}</ul>}
        </div>
      )}
      {savedNotice && !dirty && <Notice tone="ok">Modifiche salvate. Revisione {version.revision}.</Notice>}
      {conflict && (
        <div role="alert" className="rounded-xl border border-red-300 bg-red-50 px-4 py-3 text-sm text-red-900">
          <p className="font-medium">Il CE è stato modificato da qualcun altro: le tue modifiche non sono state salvate.</p>
          <p className="mt-1">Per non sovrascrivere il lavoro altrui devi ricaricare l'ultima versione (le tue modifiche andranno perse), oppure copiarle altrove prima di farlo.</p>
          <div className="mt-3 flex gap-2"><Button size="sm" variant="danger" onClick={() => void onReload()}>Ricarica l'ultima versione</Button><Button size="sm" variant="secondary" onClick={() => setConflict(false)}>Continua a modificare</Button></div>
        </div>
      )}
      <Problems error={saveError} />
      {showIssues && issues.length > 0 && (
        <div role="alert" className="rounded-xl border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-900">
          <p className="font-medium">Prima di salvare correggi questi punti:</p>
          <ul className="mt-1 list-disc pl-5">{issues.map((i) => <li key={i.id}>{i.message}</li>)}</ul>
        </div>
      )}

      <GeneralForm draft={draft} update={update} invalid={invalid} calc={calc} />

      <div className="flex items-end justify-between gap-3">
        <h2 className="text-2xl font-light">Fasi e righe</h2>
        <p className="hidden text-xs text-muted md:block">Invio scende alla riga sotto · puoi incollare celle copiate da Excel</p>
      </div>
      {draft.phases.length === 0 && <p className="card px-4 py-8 text-center text-sm text-muted">Nessuna fase: aggiungine una per iniziare.</p>}
      {draft.phases.map((phase, i) => (
        <PhaseCard key={phase.key} phase={phase} index={i} count={draft.phases.length} mode={draft.mode} months={months} calc={calc} stale={stale || state === "incomplete"}
          profiles={profiles.data ?? []} employees={employees.data ?? []} rateYear={version.rate_year} invalid={invalid} update={update} confirmRemove={setRemoving} />
      ))}
      <Button variant="secondary" onClick={() => update((d) => m.addPhase(d))}>+ Aggiungi una fase</Button>

      <div className="fixed inset-x-0 bottom-0 z-40 border-t border-ink bg-paper">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-3 px-4 py-3 sm:px-6">
          <p aria-live="polite" className="text-sm">
            {dirty ? <span className="font-medium"><span className="mr-2 inline-block h-2 w-2 rounded-full bg-amber-500" aria-hidden />Modifiche non salvate</span> : <span className="text-muted"><span className="mr-2 inline-block h-2 w-2 rounded-full bg-emerald-500" aria-hidden />Tutto salvato · revisione {version.revision}</span>}
            {issues.length > 0 && dirty && <span className="ml-3 text-amber-800">{issues.length} {issues.length === 1 ? "punto da correggere" : "punti da correggere"}</span>}
          </p>
          <div className="flex gap-2">
            <Button variant="secondary" disabled={!dirty || saving} onClick={() => { setDraft(m.draftFromDetail(detail)); setSaveError(null); setShowIssues(false); setConflict(false); }}>Annulla modifiche</Button>
            <Button variant="accent" loading={saving} disabled={!dirty} onClick={() => void save()}>Salva</Button>
          </div>
        </div>
      </div>

      <Modal open={blocker.state === "blocked"} title="Modifiche non salvate" onClose={() => blocker.state === "blocked" && blocker.reset()}
        footer={<><Button variant="secondary" onClick={() => blocker.state === "blocked" && blocker.reset()}>Resta qui</Button><Button variant="danger" onClick={() => blocker.state === "blocked" && blocker.proceed()}>Esci senza salvare</Button></>}>
        <p>Hai modifiche che non sono state salvate. Se esci le perdi.</p>
      </Modal>
      <Modal open={removing !== null} title="Elimina la fase" onClose={() => setRemoving(null)}
        footer={<><Button variant="secondary" onClick={() => setRemoving(null)}>Annulla</Button><Button variant="danger" onClick={() => { update((d) => m.removePhase(d, removing!)); setRemoving(null); }}>Elimina la fase</Button></>}>
        <p>Eliminare la fase «{phaseToRemove?.name || "senza nome"}» con le sue {phaseToRemove?.lines.length} righe? Non cambia nulla finché non salvi.</p>
      </Modal>
    </div>
  );
}
