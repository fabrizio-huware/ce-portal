import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { api, unwrap } from "../../api/client";
import { downloadFile } from "../../api/download";
import { useClients } from "../../api/lookups";
import { useAuth } from "../../auth/AuthContext";
import { BarChart, HBars, SERIES_APPROVED, SERIES_PIPELINE } from "../../components/charts/BarChart";
import { StatusBadge, Chip } from "../../components/ui/Badge";
import { FilterPanel } from "../../components/FilterPanel";
import { Button } from "../../components/ui/Button";
import { EmptyState, ErrorBox, Notice } from "../../components/ui/Feedback";
import { Menu } from "../../components/ui/Menu";
import { ScrollArea } from "../../components/ui/ScrollArea";
import { Spinner } from "../../components/ui/Spinner";
import { Stat } from "../../components/ui/Stat";
import { useDebounced } from "../../hooks/useDebounced";
import { errorMessage } from "../../lib/errors";
import { money, month, num, pct, period } from "../../lib/format";
import { DashboardHeader, EditorsOnly } from "./DashboardTabs";

export function PortfolioPage() {
  return <EditorsOnly><Portfolio /></EditorsOnly>;
}

function Portfolio() {
  const { isEditor } = useAuth();
  const clients = useClients();
  const [sp, setSp] = useSearchParams();
  const f = { from: sp.get("from") ?? "", to: sp.get("to") ?? "", client: sp.get("client") ?? "", bu: sp.get("bu") ?? "", pipeline: sp.get("pipeline") !== "0" };
  const [bu, setBu] = useState(f.bu);
  const [exportState, setExportState] = useState<{ busy: boolean; error?: string; done?: string }>({ busy: false });

  const set = (changes: Record<string, string | null>) => {
    const next = new URLSearchParams(sp);
    for (const [k, v] of Object.entries(changes)) (v ? next.set(k, v) : next.delete(k));
    setSp(next, { replace: true });
  };
  const dBu = useDebounced(bu);
  useEffect(() => { if (dBu !== f.bu) set({ bu: dBu || null }); }, [dBu]); // eslint-disable-line react-hooks/exhaustive-deps

  const query = {
    ...(f.from && { date_from: f.from }), ...(f.to && { date_to: f.to }), ...(f.client && { client_id: f.client }),
    ...(f.bu && { business_unit: f.bu }), include_pipeline: f.pipeline,
  };
  const q = useQuery({
    queryKey: ["dash-portfolio", query],
    enabled: isEditor,
    placeholderData: keepPreviousData,
    queryFn: async () => unwrap(await api.GET("/api/v1/dashboard/portfolio", { params: { query } })),
  });

  async function doExport(format: "xlsx" | "csv") {
    setExportState({ busy: true });
    try { setExportState({ busy: false, done: await downloadFile("/api/v1/dashboard/portfolio/export", { ...query, format }) }); }
    catch (e) { setExportState({ busy: false, error: errorMessage(e) }); }
  }

  const d = q.data;
  const series = f.pipeline ? [SERIES_APPROVED, SERIES_PIPELINE] : [SERIES_APPROVED];
  const monthly = (d?.by_month ?? []).map((m) => ({ label: month(m.month), values: { approved: Number(m.approved.revenue), pipeline: Number(m.pipeline.revenue) } }));
  const groups = (rows: NonNullable<typeof d>["by_client"]) => rows.map((g) => ({ label: g.label, values: { approved: Number(g.approved.revenue), pipeline: Number(g.pipeline.revenue) } })).filter((r) => r.values.approved + (f.pipeline ? r.values.pipeline : 0) > 0);
  const filtersActive = [f.from, f.to, f.client, f.bu].some(Boolean) || !f.pipeline;

  return (
    <div>
      <DashboardHeader title="Ricavi, margini e giornate dei conti economici: approvati e, a parte, la pipeline.">
        <Menu label="Esporta" loading={exportState.busy} items={[{ label: "Excel (tutte le tabelle)", onSelect: () => doExport("xlsx") }, { label: "CSV (elenco dei CE)", onSelect: () => doExport("csv") }]} />
      </DashboardHeader>

      <FilterPanel active={[f.from, f.to, f.client, f.bu].filter(Boolean).length + (f.pipeline ? 0 : 1)} columns="lg:grid-cols-5">
        <div><label htmlFor="p-from" className="label">Attivi dal</label><input id="p-from" type="date" className="field" value={f.from} onChange={(e) => set({ from: e.target.value || null })} /></div>
        <div><label htmlFor="p-to" className="label">Attivi fino al</label><input id="p-to" type="date" className="field" value={f.to} onChange={(e) => set({ to: e.target.value || null })} /></div>
        <div><label htmlFor="p-client" className="label">Cliente</label>
          <select id="p-client" className="field" value={f.client} onChange={(e) => set({ client: e.target.value || null })}>
            <option value="">Tutti i clienti</option>{clients.data?.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select></div>
        <div><label htmlFor="p-bu" className="label">Business unit</label><input id="p-bu" className="field" value={bu} onChange={(e) => setBu(e.target.value)} placeholder="es. Data" /></div>
        <div className="flex flex-col justify-end gap-2">
          <label className="flex items-center gap-2 pb-1 text-sm"><input type="checkbox" className="h-4 w-4 accent-ink" checked={f.pipeline} onChange={(e) => set({ pipeline: e.target.checked ? null : "0" })} /> Includi la pipeline</label>
          {filtersActive && <Button variant="ghost" size="sm" onClick={() => { setBu(""); setSp(new URLSearchParams(), { replace: true }); }}>Azzera filtri</Button>}
        </div>
      </FilterPanel>

      {exportState.error && <div className="mb-4"><ErrorBox message={exportState.error} /></div>}
      {exportState.done && <div className="mb-4"><Notice tone="ok">File scaricato: <strong>{exportState.done}</strong></Notice></div>}

      {q.isPending ? <div className="py-16 text-center"><Spinner label="Calcolo del portfolio…" /></div>
        : q.isError ? <ErrorBox message={errorMessage(q.error)} onRetry={() => q.refetch()} />
        : d && (
        <div className={`space-y-6 ${q.isFetching ? "opacity-70" : ""}`}>
          <section aria-label="Indicatori" className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <Stat highlight label="Ricavi approvati" value={money(d.approved.revenue)} sub={`${d.approved.count} ${d.approved.count === 1 ? "CE approvato" : "CE approvati"}`} />
            <Stat label="Margine approvato" value={money(d.approved.margin)} sub={<>Margine <strong className="text-ink">{pct(d.approved.margin_pct)}</strong> · costi {money(d.approved.cost)}</>} />
            <Stat label="Giornate approvate" value={num(d.approved.days)} sub={d.approved.count ? `${num(Number(d.approved.days) / d.approved.count)} per CE` : "—"} />
            {f.pipeline && <Stat label="Pipeline" value={money(d.pipeline.revenue)} sub={`${d.pipeline.count} CE senza ancora una versione approvata`} />}
          </section>
          {d.revisions_in_progress > 0 && <Notice>{d.revisions_in_progress === 1 ? "C'è 1 CE già approvato con una nuova versione in lavorazione" : `Ci sono ${d.revisions_in_progress} CE già approvati con una nuova versione in lavorazione`}: non {d.revisions_in_progress === 1 ? "è sommato" : "sono sommati"} alla pipeline, conta la versione approvata.</Notice>}

          {d.items.length === 0 ? <EmptyState title="Nessun conto economico nel periodo">Prova a cambiare o azzerare i filtri.</EmptyState> : (
            <>
              <section className="card p-4 sm:p-5"><BarChart title="Ricavi per mese" data={monthly} series={series} format={money} />
                <p className="mt-3 text-xs text-muted">La vista per mese esclude la contingency, che compare nei totali dei singoli CE.</p></section>
              <div className="grid gap-6 lg:grid-cols-2">
                <section className="card p-4 sm:p-5"><HBars title="Ricavi per cliente" rows={groups(d.by_client)} series={series} format={money} /></section>
                <section className="card p-4 sm:p-5"><HBars title="Ricavi per business unit" rows={groups(d.by_business_unit)} series={series} format={money} /></section>
              </div>
              <section className="card p-4 sm:p-5" aria-label="Per stato">
                <h2 className="mb-3 text-sm font-medium tracking-normal">Per stato</h2>
                <ul className="flex flex-wrap gap-3">
                  {d.by_status.map((s) => <li key={s.status} className="flex items-center gap-2 rounded-lg border border-line px-3 py-2 text-sm"><StatusBadge status={s.status} /><span className="tnum">{s.count} · {money(s.revenue)}</span></li>)}
                </ul>
              </section>
              <section aria-label="Elenco dei CE">
                <h2 className="mb-3 text-2xl font-light">Elenco dei CE</h2>
                <ScrollArea label="Elenco dei CE del portfolio" className="card">
                  <table className="w-full min-w-[60rem] border-collapse">
                    <thead className="border-b border-line bg-surface/60"><tr>
                      <th className="th">Codice</th><th className="th">Cliente</th><th className="th">Progetto</th><th className="th">Business unit</th><th className="th">Stato</th><th className="th">Periodo</th>
                      <th className="th text-right">Ricavi</th><th className="th text-right">Margine</th><th className="th text-right">Giornate</th>
                    </tr></thead>
                    <tbody className="divide-y divide-line">
                      {d.items.map((i) => (
                        <tr key={i.ce_id}>
                          <td className="td whitespace-nowrap font-medium"><Link className="underline decoration-cyan decoration-2 underline-offset-4 hover:bg-cyan" to={`/ce/${i.ce_id}`}>{i.code}</Link></td>
                          <td className="td">{i.client_name}</td><td className="td">{i.project_name}</td><td className="td">{i.business_unit ?? "—"}</td>
                          <td className="td"><span className="flex flex-wrap items-center gap-2"><StatusBadge status={i.status} />{i.scope === "pipeline" && <Chip tone="cyan">Pipeline</Chip>}</span></td>
                          <td className="td whitespace-nowrap text-muted tnum">{period(i.start_date, i.end_date)}</td>
                          <td className="td whitespace-nowrap text-right tnum">{money(i.revenue)}</td>
                          <td className="td whitespace-nowrap text-right tnum">{pct(i.margin_pct)}</td>
                          <td className="td text-right tnum">{num(i.days)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </ScrollArea>
              </section>
            </>
          )}
        </div>
      )}
    </div>
  );
}
