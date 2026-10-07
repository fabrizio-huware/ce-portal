import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { api, unwrap } from "../api/client";
import { downloadFile } from "../api/download";
import { useAuth } from "../auth/AuthContext";
import { StatusBadge } from "../components/ui/Badge";
import { EmptyState, ErrorBox, Notice } from "../components/ui/Feedback";
import { Menu } from "../components/ui/Menu";
import { Pagination } from "../components/ui/Pagination";
import { ScrollArea } from "../components/ui/ScrollArea";
import { Spinner } from "../components/ui/Spinner";
import { Button } from "../components/ui/Button";
import { useDebounced } from "../hooks/useDebounced";
import { datetime, money, pct, period } from "../lib/format";
import { errorMessage } from "../lib/errors";
import { STATUS } from "../lib/status";

const LIMIT = 20;

type Row = {
  id: string; code: string; client: string; project: string; start: string; end: string; version: number;
  status?: string; owner?: string; price: string | null; marginPct?: string | null; stamp?: string | null;
};

type Filters = { project: string; code: string; client_id: string; status: string; date_from: string; date_to: string; mine: boolean; page: number };

function readFilters(sp: URLSearchParams): Filters {
  return {
    project: sp.get("project") ?? "", code: sp.get("code") ?? "", client_id: sp.get("client_id") ?? "",
    status: sp.get("status") ?? "", date_from: sp.get("date_from") ?? "", date_to: sp.get("date_to") ?? "",
    mine: sp.get("mine") === "1", page: Math.max(1, Number(sp.get("page") ?? 1) || 1),
  };
}

export function CeListPage() {
  const { user, isEditor } = useAuth();
  const [sp, setSp] = useSearchParams();
  const f = readFilters(sp);
  const [project, setProject] = useState(f.project);
  const [code, setCode] = useState(f.code);
  const [showFilters, setShowFilters] = useState(false);
  const [exportError, setExportError] = useState<string | null>(null);
  const [exported, setExported] = useState<string | null>(null);
  const [exporting, setExporting] = useState(false);

  const setParams = (changes: Record<string, string | null>, keepPage = false) => {
    const next = new URLSearchParams(sp);
    for (const [k, v] of Object.entries(changes)) (v ? next.set(k, v) : next.delete(k));
    if (!keepPage) next.delete("page");
    setSp(next, { replace: true });
  };

  // I campi di testo aggiornano l'indirizzo dopo una breve pausa di digitazione.
  const dProject = useDebounced(project);
  const dCode = useDebounced(code);
  useEffect(() => { if (dProject !== f.project) setParams({ project: dProject || null }); }, [dProject]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { if (dCode !== f.code) setParams({ code: dCode || null }); }, [dCode]); // eslint-disable-line react-hooks/exhaustive-deps

  const clients = useQuery({
    queryKey: ["clients-lookup"],
    queryFn: async () => unwrap(await api.GET("/api/v1/clients/lookup", { params: { query: { limit: 200 } } })),
    staleTime: 5 * 60_000,
  });

  const apiQuery = {
    ...(f.client_id && { client_id: f.client_id }),
    ...(f.project && { project: f.project }),
    ...(f.code && { code: f.code }),
    ...(f.date_from && { date_from: f.date_from }),
    ...(f.date_to && { date_to: f.date_to }),
    ...(isEditor && f.status && { status: f.status as "draft" }),
    ...(isEditor && f.mine && user && { created_by: user.id }),
  };

  const list = useQuery({
    queryKey: ["ce-list", isEditor, apiQuery, f.page],
    placeholderData: keepPreviousData,
    queryFn: async (): Promise<{ rows: Row[]; total: number }> => {
      const paging = { limit: LIMIT, offset: (f.page - 1) * LIMIT };
      if (isEditor) {
        const page = unwrap(await api.GET("/api/v1/ce", { params: { query: { ...apiQuery, ...paging } } }));
        return {
          total: page.total,
          rows: page.items.map((i) => ({
            id: i.ce_id, code: i.code, client: i.client.name, project: i.project_name, start: i.start_date, end: i.end_date,
            version: i.version_number, status: i.status, owner: i.owner.full_name, price: i.price ?? null,
            marginPct: i.margin_pct ?? null, stamp: i.updated_at,
          })),
        };
      }
      const page = unwrap(await api.GET("/api/v1/ce/summaries", { params: { query: { ...apiQuery, ...paging } } }));
      return {
        total: page.total,
        rows: page.items.map((i) => ({
          id: i.ce_id, code: i.code, client: i.client_name, project: i.project_name, start: i.start_date, end: i.end_date,
          version: i.version_number, price: i.price ?? null, stamp: i.approved_at ?? null,
        })),
      };
    },
  });

  async function exportList(format: "xlsx" | "csv") {
    setExportError(null);
    setExported(null);
    setExporting(true);
    try {
      const path = isEditor ? "/api/v1/ce/export" : "/api/v1/ce/summaries/export";
      setExported(await downloadFile(path, { ...apiQuery, format }));
    } catch (e) {
      setExportError(errorMessage(e));
    } finally {
      setExporting(false);
    }
  }

  const activeFilters = [f.project, f.code, f.client_id, f.status, f.date_from, f.date_to, f.mine ? "1" : ""].filter(Boolean).length;
  const rows = list.data?.rows ?? [];
  const total = list.data?.total ?? 0;

  return (
    <div>
      <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-4xl font-light sm:text-5xl">Conti economici</h1>
          <p className="mt-2 text-sm text-muted">
            {isEditor ? "Cerca, apri e controlla i conti economici di progetto." : "Conti economici approvati: giornate e ricavi per fase."}
          </p>
        </div>
        <Menu label="Esporta elenco" loading={exporting} items={[
          { label: "Excel (.xlsx)", onSelect: () => exportList("xlsx") },
          { label: "CSV per Excel", onSelect: () => exportList("csv") },
        ]} />
      </div>

      <section aria-label="Filtri" className="card mb-6 p-4">
        <div className="flex items-center justify-between gap-3 md:hidden">
          <Button variant="secondary" size="sm" aria-expanded={showFilters} onClick={() => setShowFilters((s) => !s)}>
            Filtri{activeFilters > 0 && <span className="rounded-full bg-cyan px-1.5 text-xs">{activeFilters}</span>}
          </Button>
        </div>
        <div className={`${showFilters ? "mt-4 grid" : "hidden"} grid-cols-1 gap-4 sm:grid-cols-2 md:mt-0 md:grid lg:grid-cols-4`}>
          <div><label htmlFor="f-code" className="label">Codice</label><input id="f-code" className="field" value={code} onChange={(e) => setCode(e.target.value)} placeholder="es. PS-BONGA" /></div>
          <div><label htmlFor="f-project" className="label">Progetto</label><input id="f-project" className="field" value={project} onChange={(e) => setProject(e.target.value)} placeholder="Nome del progetto" /></div>
          <div>
            <label htmlFor="f-client" className="label">Cliente</label>
            <select id="f-client" className="field" value={f.client_id} onChange={(e) => setParams({ client_id: e.target.value || null })}>
              <option value="">Tutti i clienti</option>
              {clients.data?.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
          </div>
          {isEditor && (
            <div>
              <label htmlFor="f-status" className="label">Stato</label>
              <select id="f-status" className="field" value={f.status} onChange={(e) => setParams({ status: e.target.value || null })}>
                <option value="">Tutti gli stati</option>
                {Object.entries(STATUS).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}
              </select>
            </div>
          )}
          <div><label htmlFor="f-from" className="label">Attivi dal</label><input id="f-from" type="date" className="field" value={f.date_from} onChange={(e) => setParams({ date_from: e.target.value || null })} /></div>
          <div><label htmlFor="f-to" className="label">Attivi fino al</label><input id="f-to" type="date" className="field" value={f.date_to} onChange={(e) => setParams({ date_to: e.target.value || null })} /></div>
          {isEditor && (
            <label className="flex items-end gap-2 pb-2 text-sm"><input type="checkbox" className="h-4 w-4 accent-ink" checked={f.mine} onChange={(e) => setParams({ mine: e.target.checked ? "1" : null })} /> Solo i miei CE</label>
          )}
          {activeFilters > 0 && (
            <div className="flex items-end"><Button variant="ghost" size="sm" onClick={() => { setProject(""); setCode(""); setSp(new URLSearchParams(), { replace: true }); }}>Azzera filtri</Button></div>
          )}
        </div>
      </section>

      {exportError && <div className="mb-4"><ErrorBox message={exportError} /></div>}
      {exported && <div className="mb-4"><Notice tone="ok">File scaricato: <strong>{exported}</strong></Notice></div>}

      <p aria-live="polite" className="mb-3 flex items-center gap-3 text-sm text-muted tnum">
        {list.isPending ? <Spinner label="Caricamento…" /> : <span><strong className="text-ink">{total}</strong> {total === 1 ? "conto economico" : "conti economici"}</span>}
        {list.isFetching && !list.isPending && <Spinner />}
      </p>

      {list.isError ? (
        <ErrorBox message={errorMessage(list.error)} onRetry={() => list.refetch()} />
      ) : !list.isPending && rows.length === 0 ? (
        <EmptyState title={activeFilters ? "Nessun risultato" : "Nessun conto economico"}>
          {activeFilters ? "Prova a cambiare o azzerare i filtri." : isEditor ? "Quando ne creerai uno, comparirà qui." : "Quando un conto economico verrà approvato, comparirà qui."}
        </EmptyState>
      ) : (
        <>
          <ScrollArea label="Elenco dei conti economici" className="card hidden md:block">
            <table className="w-full min-w-[56rem] border-collapse">
              <thead className="border-b border-line bg-surface/60">
                <tr>
                  <th className="th">Codice</th><th className="th">Cliente</th><th className="th">Progetto</th><th className="th">Periodo</th>
                  <th className="th">{isEditor ? "Stato" : "Versione"}</th>
                  {isEditor && <th className="th">Autore</th>}
                  <th className="th text-right">Prezzo</th>
                  {isEditor && <th className="th text-right">Margine</th>}
                  <th className="th">{isEditor ? "Aggiornato" : "Approvato il"}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {rows.map((r) => (
                  <tr key={r.id} className="hover:bg-surface/50">
                    <td className="td whitespace-nowrap font-medium"><Link to={`/ce/${r.id}`} className="underline decoration-cyan decoration-2 underline-offset-4 hover:bg-cyan">{r.code}</Link></td>
                    <td className="td">{r.client}</td>
                    <td className="td">{r.project}</td>
                    <td className="td whitespace-nowrap tnum text-muted">{period(r.start, r.end)}</td>
                    <td className="td">{r.status ? <span className="flex items-center gap-2"><StatusBadge status={r.status} /><span className="text-xs text-muted">v{r.version}</span></span> : `v${r.version}`}</td>
                    {isEditor && <td className="td whitespace-nowrap">{r.owner}</td>}
                    <td className="td whitespace-nowrap text-right tnum">{money(r.price)}</td>
                    {isEditor && <td className="td whitespace-nowrap text-right tnum">{pct(r.marginPct)}</td>}
                    <td className="td whitespace-nowrap text-muted tnum">{datetime(r.stamp)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </ScrollArea>
          <ul className="space-y-3 md:hidden">
            {rows.map((r) => (
              <li key={r.id}>
                <Link to={`/ce/${r.id}`} className="card block p-4 active:bg-surface">
                  <div className="flex items-start justify-between gap-3">
                    <span className="font-medium">{r.code}</span>
                    {r.status ? <StatusBadge status={r.status} /> : <span className="text-xs text-muted">v{r.version}</span>}
                  </div>
                  <div className="mt-1 text-sm">{r.client} · {r.project}</div>
                  <div className="mt-1 text-xs text-muted tnum">{period(r.start, r.end)}</div>
                  <div className="mt-3 flex items-baseline justify-between border-t border-line pt-3">
                    <span className="text-lg font-light tnum">{money(r.price)}</span>
                    {isEditor && <span className="text-xs text-muted">margine <span className="font-medium text-ink tnum">{pct(r.marginPct)}</span></span>}
                  </div>
                </Link>
              </li>
            ))}
          </ul>
          <Pagination total={total} limit={LIMIT} offset={(f.page - 1) * LIMIT} onChange={(offset) => setParams({ page: String(offset / LIMIT + 1) }, true)} />
        </>
      )}
    </div>
  );
}
