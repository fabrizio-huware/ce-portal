import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import { useState } from "react";

import { api, unwrap } from "../../api/client";
import { downloadFile } from "../../api/download";
import { useClients, useEmployees, useProfiles } from "../../api/lookups";
import { useAuth } from "../../auth/AuthContext";
import { FilterPanel } from "../../components/FilterPanel";
import { Button } from "../../components/ui/Button";
import { EmptyState, ErrorBox, Notice } from "../../components/ui/Feedback";
import { Menu } from "../../components/ui/Menu";
import { ScrollArea } from "../../components/ui/ScrollArea";
import { Spinner } from "../../components/ui/Spinner";
import { Stat } from "../../components/ui/Stat";
import { errorMessage } from "../../lib/errors";
import { month, num } from "../../lib/format";
import { HEAT_CLASS, heatLevel } from "../../lib/scale";
import { DashboardHeader, EditorsOnly } from "./DashboardTabs";

export function ResourcesPage() {
  return <EditorsOnly><Resources /></EditorsOnly>;
}

const LEGEND = [
  { level: "empty" as const, text: "nessun impegno" }, { level: "low" as const, text: "fino al 50%" },
  { level: "high" as const, text: "fino al 100%" }, { level: "over" as const, text: "oltre il 100%: sovraccarico" },
];

function Resources() {
  const { isEditor } = useAuth();
  const clients = useClients();
  const profiles = useProfiles();
  const employees = useEmployees();
  const [sp, setSp] = useSearchParams();
  const f = { from: sp.get("from") ?? "", to: sp.get("to") ?? "", client: sp.get("client") ?? "", profile: sp.get("profile") ?? "", employee: sp.get("employee") ?? "", pipeline: sp.get("pipeline") === "1" };
  const [exportState, setExportState] = useState<{ busy: boolean; error?: string; done?: string }>({ busy: false });
  const set = (changes: Record<string, string | null>) => {
    const next = new URLSearchParams(sp);
    for (const [k, v] of Object.entries(changes)) (v ? next.set(k, v) : next.delete(k));
    setSp(next, { replace: true });
  };

  const query = {
    ...(f.from && { date_from: `${f.from}-01` }), ...(f.to && { date_to: `${f.to}-01` }), ...(f.client && { client_id: f.client }),
    ...(f.profile && { profile_id: f.profile }), ...(f.employee && { employee_id: f.employee }), include_pipeline: f.pipeline,
  };
  const q = useQuery({
    queryKey: ["dash-resources", query],
    enabled: isEditor,
    placeholderData: keepPreviousData,
    retry: false,
    queryFn: async () => unwrap(await api.GET("/api/v1/dashboard/resources", { params: { query } })),
  });
  async function doExport(format: "xlsx" | "csv") {
    setExportState({ busy: true });
    try { setExportState({ busy: false, done: await downloadFile("/api/v1/dashboard/resources/export", { ...query, format }) }); }
    catch (e) { setExportState({ busy: false, error: errorMessage(e) }); }
  }

  const d = q.data;
  const overloadedPeople = d?.employees.filter((e) => e.overloaded_months > 0) ?? [];
  let peak: { name: string; month: string; fte: number } | null = null;
  d?.employees.forEach((e) => e.cells.forEach((c, i) => { const v = Number(c.fte ?? 0); if (!peak || v > peak.fte) peak = { name: e.name, month: d.months[i].month, fte: v }; }));
  const totalDays = d?.profiles.reduce((s, p) => s + Number(p.total_days), 0) ?? 0;
  const filtersActive = Boolean(f.from || f.to || f.client || f.profile || f.employee || f.pipeline);

  return (
    <div>
      <DashboardHeader title="Impegno delle persone mese per mese: 100% è una persona a tempo pieno sui giorni lavorativi del calendario generale.">
        <Menu label="Esporta" loading={exportState.busy} items={[{ label: "Excel (collaboratori, profili, dati)", onSelect: () => doExport("xlsx") }, { label: "CSV (dati per mese)", onSelect: () => doExport("csv") }]} />
      </DashboardHeader>

      <FilterPanel active={[f.from, f.to, f.client, f.profile, f.employee].filter(Boolean).length + (f.pipeline ? 1 : 0)} columns="lg:grid-cols-6">
        <div><label htmlFor="r-from" className="label">Dal mese</label><input id="r-from" type="month" className="field" value={f.from} onChange={(e) => set({ from: e.target.value || null })} /></div>
        <div><label htmlFor="r-to" className="label">Al mese</label><input id="r-to" type="month" className="field" value={f.to} onChange={(e) => set({ to: e.target.value || null })} /></div>
        <div><label htmlFor="r-client" className="label">Cliente</label>
          <select id="r-client" className="field" value={f.client} onChange={(e) => set({ client: e.target.value || null })}><option value="">Tutti</option>{clients.data?.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</select></div>
        <div><label htmlFor="r-profile" className="label">Profilo</label>
          <select id="r-profile" className="field" value={f.profile} onChange={(e) => set({ profile: e.target.value || null })}><option value="">Tutti</option>{profiles.data?.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}</select></div>
        <div><label htmlFor="r-emp" className="label">Collaboratore</label>
          <select id="r-emp" className="field" value={f.employee} onChange={(e) => set({ employee: e.target.value || null })}><option value="">Tutti</option>{employees.data?.map((e) => <option key={e.id} value={e.id}>{e.last_name} {e.first_name}</option>)}</select></div>
        <div className="flex flex-col justify-end gap-2">
          <label className="flex items-center gap-2 pb-1 text-sm"><input type="checkbox" className="h-4 w-4 accent-ink" checked={f.pipeline} onChange={(e) => set({ pipeline: e.target.checked ? "1" : null })} /> Includi la pipeline</label>
          {filtersActive && <Button variant="ghost" size="sm" onClick={() => setSp(new URLSearchParams(), { replace: true })}>Azzera filtri</Button>}
        </div>
      </FilterPanel>

      {exportState.error && <div className="mb-4"><ErrorBox message={exportState.error} /></div>}
      {exportState.done && <div className="mb-4"><Notice tone="ok">File scaricato: <strong>{exportState.done}</strong></Notice></div>}

      {q.isPending ? <div className="py-16 text-center"><Spinner label="Calcolo del carico…" /></div>
        : q.isError ? <ErrorBox message={errorMessage(q.error)} onRetry={() => q.refetch()} />
        : d && (
        <div className={`space-y-6 ${q.isFetching ? "opacity-70" : ""}`}>
          <p className="text-sm text-muted">Periodo: <strong className="text-ink">{month(d.date_from)} – {month(d.date_to)}</strong> · {d.ces_count} {d.ces_count === 1 ? "CE considerato" : "CE considerati"} ({d.include_pipeline ? "approvati e pipeline" : "solo approvati"}).</p>
          <section aria-label="Indicatori" className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <Stat highlight={overloadedPeople.length > 0} label="Persone in sovraccarico" value={overloadedPeople.length} sub={overloadedPeople.length ? overloadedPeople.map((p) => p.name).slice(0, 3).join(", ") + (overloadedPeople.length > 3 ? "…" : "") : "nessuno oltre il 100%"} />
            <Stat label="Picco di impegno" value={peak ? `${Math.round((peak as { fte: number }).fte * 100)}%` : "—"} sub={peak ? `${(peak as { name: string }).name}, ${month((peak as { month: string }).month)}` : undefined} />
            <Stat label="Giornate pianificate" value={num(totalDays)} sub={`${d.employees.length} collaboratori · ${d.profiles.length} profili`} />
            <Stat label="Soglia di sovraccarico" value="100%" sub="1 FTE in un mese" />
          </section>

          {d.employees.length === 0 && d.profiles.length === 0 ? <EmptyState title="Nessun impegno nel periodo">Prova ad ampliare il periodo o ad azzerare i filtri.</EmptyState> : (
            <>
              <section aria-label="Impegno dei collaboratori">
                <h2 className="mb-1 text-2xl font-light">Impegno dei collaboratori</h2>
                <ul className="mb-3 flex flex-wrap gap-3 text-xs text-muted" aria-label="Legenda">
                  {LEGEND.map((l) => <li key={l.level} className="flex items-center gap-2"><span className={`inline-block h-4 w-8 rounded-sm border border-ink/40 ${HEAT_CLASS[l.level]}`} aria-hidden />{l.text}</li>)}
                </ul>
                {d.employees.length === 0 ? <p className="card px-4 py-6 text-sm text-muted">Nessuna riga ha un collaboratore assegnato nel periodo (vedi i profili qui sotto).</p> : (
                  <ScrollArea label="Impegno dei collaboratori per mese" className="card">
                    <table className="w-full border-collapse" style={{ minWidth: `${16 + d.months.length * 5}rem` }}>
                      <thead className="border-b border-line bg-surface/60">
                        <tr><th scope="col" className="th">Collaboratore</th>{d.months.map((m) => <th key={m.month} scope="col" className="th text-center">{month(m.month)}</th>)}<th scope="col" className="th text-right">Giorni</th><th scope="col" className="th text-right">Mesi &gt; 100%</th></tr>
                        <tr className="text-[11px] text-muted"><th scope="row" className="px-3 pb-2 text-left font-normal">Giorni lavorativi del mese</th>{d.months.map((m) => <td key={m.month} className="px-3 pb-2 text-center tnum">{m.capacity_days}</td>)}<td /><td /></tr>
                      </thead>
                      <tbody className="divide-y divide-line">
                        {d.employees.map((e) => (
                          <tr key={e.id ?? e.name}>
                            <th scope="row" className="td whitespace-nowrap text-left font-medium">{e.name}{e.profile_name && <span className="block text-xs font-normal text-muted">{e.profile_name}</span>}</th>
                            {e.cells.map((c, i) => {
                              const level = heatLevel(c.fte === null || c.fte === undefined ? null : Number(c.fte), c.overloaded);
                              const label = c.fte === null || c.fte === undefined || Number(c.days) === 0 ? "—" : `${c.overloaded ? "⚠ " : ""}${Math.round(Number(c.fte) * 100)}%`;
                              const split = d.include_pipeline && Number(c.days_pipeline) > 0 ? ` (approvati ${num(c.days_approved)}, pipeline ${num(c.days_pipeline)})` : "";
                              return (
                                <td key={d.months[i].month} className={`px-1 py-1 text-center text-sm tnum ${HEAT_CLASS[level]}`} title={`${e.name}, ${month(d.months[i].month)}: ${num(c.days)} giorni${split}`}>
                                  <span aria-label={Number(c.days) === 0 ? `${month(d.months[i].month)}: nessun impegno` : `${month(d.months[i].month)}: ${Math.round(Number(c.fte) * 100)}%${c.overloaded ? ", sovraccarico" : ""}, ${num(c.days)} giorni${split}`}>{label}</span>
                                </td>
                              );
                            })}
                            <td className="td text-right tnum">{num(e.total_days)}</td>
                            <td className="td text-right tnum">{e.overloaded_months || "—"}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </ScrollArea>
                )}
              </section>
              <section aria-label="Giornate per profilo">
                <h2 className="mb-3 text-2xl font-light">Giornate per profilo</h2>
                <ScrollArea label="Giornate per profilo e mese" className="card">
                  <table className="w-full border-collapse" style={{ minWidth: `${20 + d.months.length * 4.2}rem` }}>
                    <thead className="border-b border-line bg-surface/60"><tr><th scope="col" className="th">Profilo</th>{d.months.map((m) => <th key={m.month} scope="col" className="th text-right">{month(m.month)}</th>)}<th scope="col" className="th text-right">Totale</th><th scope="col" className="th text-right" title="Giornate di righe senza un collaboratore assegnato">Non assegnato</th></tr></thead>
                    <tbody className="divide-y divide-line">
                      {d.profiles.map((p) => (
                        <tr key={p.id ?? p.name}><th scope="row" className="td whitespace-nowrap text-left font-medium">{p.name}</th>
                          {p.cells.map((c, i) => <td key={d.months[i].month} className="td text-right tnum">{Number(c.days) === 0 ? "—" : num(c.days)}</td>)}
                          <td className="td text-right font-semibold tnum">{num(p.total_days)}</td><td className="td text-right tnum text-muted">{Number(p.unassigned_days) === 0 ? "—" : num(p.unassigned_days)}</td></tr>
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
