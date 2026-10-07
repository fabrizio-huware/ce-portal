import { useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";

import { api, unwrap } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { Problems } from "../components/ActionsBar";
import { ClientSelect } from "../components/ClientSelect";
import { Button } from "../components/ui/Button";
import { ErrorBox } from "../components/ui/Feedback";
import { errorDetails } from "../lib/errors";
import { monthsBetween } from "../editor/model";
import { numberError, parseNumber } from "../editor/numbers";

export function NewCePage() {
  const { isEditor } = useAuth();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [f, setF] = useState({ code: "", clientId: "", project: "", start: "", end: "", mode: "hours" as "hours" | "percent", bu: "", sf: "", discount: "", standard: true });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<{ message: string; issues: string[] } | null>(null);
  const [touched, setTouched] = useState(false);

  if (!isEditor) return <ErrorBox message="Non hai i permessi per creare conti economici." />;

  const problems: string[] = [];
  if (!f.code.trim()) problems.push("Indica il codice del CE");
  if (!f.clientId) problems.push("Scegli il cliente");
  if (!f.project.trim()) problems.push("Indica il nome del progetto");
  if (!f.start || !f.end) problems.push("Indica le date di inizio e fine");
  else if (f.end < f.start) problems.push("La data di fine precede quella di inizio");
  else if (monthsBetween(f.start, f.end).length > 12) problems.push("Il periodo non può superare 12 mesi");
  const discountError = numberError(f.discount, { max: 100 });
  if (discountError) problems.push(`Max sconto: ${discountError.toLowerCase()}`);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setTouched(true);
    if (problems.length) return;
    setBusy(true);
    setError(null);
    try {
      const created = unwrap(await api.POST("/api/v1/ce", {
        body: {
          code: f.code.trim(), client_id: f.clientId, project_name: f.project.trim(), start_date: f.start, end_date: f.end, planning_mode: f.mode,
          business_unit: f.bu.trim() || null, sf_opportunity: f.sf.trim() || null, max_discount_pct: parseNumber(f.discount) || "0", standard_phases: f.standard,
        },
      }));
      await qc.invalidateQueries({ queryKey: ["ce-list"] });
      navigate(`/ce/${created.ce.id}/modifica`);
    } catch (err) {
      setError(errorDetails(err));
    } finally {
      setBusy(false);
    }
  }

  const bad = (cond: boolean) => (touched && cond ? "border-red-600" : "");
  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <Link to="/ce" className="inline-flex items-center gap-1 text-sm font-medium text-teal-700 underline-offset-4 hover:underline">← Tutti i conti economici</Link>
      <div><h1 className="text-4xl font-light sm:text-5xl">Nuovo conto economico</h1><p className="mt-2 text-sm text-muted">Compili prima i dati generali; le righe si inseriscono nella schermata successiva.</p></div>
      <form onSubmit={submit} noValidate className="card space-y-5 p-5 sm:p-6" aria-label="Nuovo conto economico">
        <Problems error={error} />
        {touched && problems.length > 0 && <div role="alert" className="rounded-xl border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-900"><p className="font-medium">Prima di continuare:</p><ul className="mt-1 list-disc pl-5">{problems.map((p) => <li key={p}>{p}</li>)}</ul></div>}
        <div className="grid gap-5 sm:grid-cols-2">
          <div><label htmlFor="n-code" className="label">Codice del CE</label><input id="n-code" className={`field ${bad(!f.code.trim())}`} value={f.code} onChange={(e) => setF({ ...f, code: e.target.value })} placeholder="es. PS-CLIENTE-PROGETTO-PJT" maxLength={60} /></div>
          <div><label htmlFor="n-client" className="label">Cliente</label><ClientSelect id="n-client" value={f.clientId} onChange={(clientId) => setF({ ...f, clientId })} invalid={touched && !f.clientId} /></div>
          <div className="sm:col-span-2"><label htmlFor="n-project" className="label">Nome del progetto</label><input id="n-project" className={`field ${bad(!f.project.trim())}`} value={f.project} onChange={(e) => setF({ ...f, project: e.target.value })} maxLength={300} /></div>
          <div><label htmlFor="n-start" className="label">Inizio</label><input id="n-start" type="date" className={`field ${bad(!f.start)}`} value={f.start} onChange={(e) => setF({ ...f, start: e.target.value })} /></div>
          <div><label htmlFor="n-end" className="label">Fine</label><input id="n-end" type="date" className={`field ${bad(!f.end || f.end < f.start)}`} value={f.end} onChange={(e) => setF({ ...f, end: e.target.value })} /></div>
          <fieldset className="sm:col-span-2"><legend className="label">Come pianifichi le attività</legend>
            <div className="grid gap-3 sm:grid-cols-2">
              <label className="flex cursor-pointer gap-3 rounded-xl border border-line p-3 has-[:checked]:border-ink has-[:checked]:bg-surface"><input type="radio" name="mode" className="mt-1 accent-ink" checked={f.mode === "hours"} onChange={() => setF({ ...f, mode: "hours" })} /><span><strong className="block text-sm">A ore</strong><span className="text-xs text-muted">Indichi le ore di ogni riga; il portale le distribuisce sui mesi.</span></span></label>
              <label className="flex cursor-pointer gap-3 rounded-xl border border-line p-3 has-[:checked]:border-ink has-[:checked]:bg-surface"><input type="radio" name="mode" className="mt-1 accent-ink" checked={f.mode === "percent"} onChange={() => setF({ ...f, mode: "percent" })} /><span><strong className="block text-sm">A percentuali mensili</strong><span className="text-xs text-muted">Indichi per ogni riga la % di impegno di ogni mese.</span></span></label>
            </div>
          </fieldset>
          <div><label htmlFor="n-bu" className="label">Business unit (facoltativa)</label><input id="n-bu" className="field" value={f.bu} onChange={(e) => setF({ ...f, bu: e.target.value })} maxLength={100} /></div>
          <div><label htmlFor="n-sf" className="label">Opportunità Salesforce (facoltativa)</label><input id="n-sf" className="field" value={f.sf} onChange={(e) => setF({ ...f, sf: e.target.value })} maxLength={100} /></div>
          <div><label htmlFor="n-disc" className="label">Max sconto % (facoltativo)</label><input id="n-disc" inputMode="decimal" className={`field text-right ${bad(!!discountError)}`} value={f.discount} onChange={(e) => setF({ ...f, discount: e.target.value })} placeholder="0" /></div>
          <label className="flex items-start gap-2 text-sm sm:pt-6"><input type="checkbox" className="mt-0.5 h-4 w-4 shrink-0 accent-ink" checked={f.standard} onChange={(e) => setF({ ...f, standard: e.target.checked })} /> Parti dalle fasi standard (Project Management, Analysis, …)</label>
        </div>
        <div className="flex justify-end gap-2 border-t border-line pt-5"><Link to="/ce" className="inline-flex items-center rounded-lg px-4 py-2.5 text-sm font-medium hover:bg-surface">Annulla</Link><Button type="submit" variant="accent" loading={busy}>Crea e inizia a compilare</Button></div>
      </form>
    </div>
  );
}
