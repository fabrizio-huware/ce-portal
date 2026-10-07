import { useQuery } from "@tanstack/react-query";
import { useState, type ReactNode } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";

import { api, unwrap } from "../api/client";
import { downloadFile } from "../api/download";
import type { CeDetail, ViewerCe } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { Chip, StatusBadge } from "../components/ui/Badge";
import { EmptyState, ErrorBox, Notice } from "../components/ui/Feedback";
import { Menu } from "../components/ui/Menu";
import { ScrollArea } from "../components/ui/ScrollArea";
import { Spinner } from "../components/ui/Spinner";
import { errorMessage } from "../lib/errors";
import { date, datetime, money, month, num, pct, period, points } from "../lib/format";
import { HISTORY_LABEL, MODE_LABEL } from "../lib/status";

export function CeDetailPage() {
  const { id = "" } = useParams();
  const { isEditor } = useAuth();
  const [sp] = useSearchParams();
  const version = sp.get("v");

  const detail = useQuery({
    queryKey: ["ce", id, isEditor, version],
    queryFn: async () => {
      if (!isEditor) return unwrap(await api.GET("/api/v1/ce/summaries/{ce_id}", { params: { path: { ce_id: id } } }));
      if (version) return unwrap(await api.GET("/api/v1/ce/{ce_id}/versions/{number}", { params: { path: { ce_id: id, number: Number(version) } } }));
      return unwrap(await api.GET("/api/v1/ce/{ce_id}", { params: { path: { ce_id: id } } }));
    },
  });

  if (detail.isPending) return <div className="py-20 text-center"><Spinner label="Caricamento del conto economico…" /></div>;
  if (detail.isError) {
    return (
      <div className="space-y-4">
        <BackLink />
        <ErrorBox message={errorMessage(detail.error)} onRetry={() => detail.refetch()} />
      </div>
    );
  }
  return isEditor ? <EditorView detail={detail.data as CeDetail} requestedVersion={version} /> : <ViewerView ce={detail.data as ViewerCe} />;
}

function BackLink() {
  return <Link to="/ce" className="inline-flex items-center gap-1 text-sm font-medium text-teal-700 underline-offset-4 hover:underline">← Tutti i conti economici</Link>;
}

function useExport() {
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  async function run(path: string, params: Record<string, string | number | undefined>) {
    setError(null); setDone(null); setBusy(true);
    try { setDone(await downloadFile(path, params)); } catch (e) { setError(errorMessage(e)); } finally { setBusy(false); }
  }
  return { error, done, busy, run };
}

function Feedback({ exp }: { exp: ReturnType<typeof useExport> }) {
  return (
    <>
      {exp.error && <ErrorBox message={exp.error} />}
      {exp.done && <Notice tone="ok">File scaricato: <strong>{exp.done}</strong></Notice>}
    </>
  );
}

function Kpi({ label, value, sub, highlight, wide, compact }: { label: string; value: ReactNode; sub?: ReactNode; highlight?: boolean; wide?: boolean; compact?: boolean }) {
  return (
    <div className={`card ${compact ? "p-3 sm:p-4" : "p-4"} ${wide ? "col-span-2 lg:col-span-2" : ""}`}>
      <div className="label !mb-2">{label}</div>
      <div className={`whitespace-nowrap font-light tracking-tightest tnum ${compact ? "text-xl sm:text-[1.7rem]" : "text-2xl sm:text-[1.7rem]"}`}>{highlight ? <span className="hl">{value}</span> : value}</div>
      {sub && <div className="mt-1.5 text-xs text-muted tnum">{sub}</div>}
    </div>
  );
}

// ======================================================================= vista completa (admin, presale)
type Tab = "dettaglio" | "riepilogo" | "staffing" | "versioni" | "storico";
const TABS: { id: Tab; label: string }[] = [
  { id: "dettaglio", label: "Dettaglio" }, { id: "riepilogo", label: "Riepilogo" }, { id: "staffing", label: "Staffing mensile" },
  { id: "versioni", label: "Versioni" }, { id: "storico", label: "Storico" },
];

function EditorView({ detail, requestedVersion }: { detail: CeDetail; requestedVersion: string | null }) {
  const [tab, setTab] = useState<Tab>("dettaglio");
  const exp = useExport();
  const { ce, version, header, calculation: calc } = detail;
  const k = calc.kpis;
  const base = `/api/v1/ce/${ce.id}/export`;
  const v = { version: requestedVersion ?? undefined };

  return (
    <div className="space-y-6">
      <BackLink />
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-3">
            <h1 className="break-words text-3xl font-light sm:text-5xl">{ce.code}</h1>
            <StatusBadge status={version.status} />
            <Chip>v{version.number}{ce.versions_count > 1 ? ` di ${ce.versions_count}` : ""}</Chip>
          </div>
          <p className="mt-2 text-base sm:text-lg">{header.client.name} <span className="text-muted">·</span> {header.project_name}</p>
        </div>
        <Menu variant="accent" label="Esporta" loading={exp.busy} items={[
          { label: "Excel completo", hint: "Con formule modificabili", onSelect: () => exp.run(base, { format: "xlsx", ...v }) },
          { label: "PDF completo", hint: "Uso interno", onSelect: () => exp.run(base, { format: "pdf", ...v }) },
          { label: "CSV delle righe", onSelect: () => exp.run(base, { format: "csv", ...v }) },
          "separator",
          { label: "Riepilogo PDF", hint: "Senza costi né righe: si può condividere", onSelect: () => exp.run(base, { format: "pdf", variant: "summary", ...v }) },
          { label: "Riepilogo Excel", onSelect: () => exp.run(base, { format: "xlsx", variant: "summary", ...v }) },
        ]} />
      </div>
      <Feedback exp={exp} />
      {requestedVersion && Number(requestedVersion) !== ce.versions_count && (
        <Notice>Stai guardando la versione {version.number}, non l'ultima. <Link className="font-medium underline" to={`/ce/${ce.id}`}>Vai all'ultima versione</Link></Notice>
      )}
      {version.status === "rejected" && version.rejection_reason && (
        <ErrorBox message={`Rifiutato${version.rejected_by ? ` da ${version.rejected_by.full_name}` : ""}: ${version.rejection_reason}`} />
      )}

      <dl className="grid grid-cols-2 gap-x-6 gap-y-3 text-sm sm:grid-cols-3 lg:grid-cols-6">
        {[
          ["Periodo", period(header.start_date, header.end_date)], ["Modalità", MODE_LABEL[header.planning_mode]],
          ["Autore", ce.owner.full_name], ["Business unit", header.business_unit ?? "—"],
          ["Opportunità SF", header.sf_opportunity ?? "—"], ["Tariffe", `Listino ${version.rate_year}`],
        ].map(([label, value]) => (
          <div key={label}><dt className="label !mb-0.5">{label}</dt><dd className="tnum">{value}</dd></div>
        ))}
      </dl>

      <section aria-label="Indicatori" className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Kpi highlight wide label="Prezzo progetto" value={money(k.price_project)} sub={`Sconto massimo ${points(k.max_discount_pct)}`} />
        <Kpi label="Margine" value={money(calc.total.margin)} sub={<>Margine <strong className="text-ink">{pct(calc.total.margin_pct)}</strong></>} />
        <Kpi label="Costi" value={money(calc.total.cost)} sub={<>C/R <strong className="text-ink">{pct(calc.total.cost_ratio)}</strong></>} />
        <Kpi label="Prezzo minimo" value={money(k.price_min)} sub="Dopo lo sconto massimo" />
        <Kpi label="Giornate" value={num(k.days_total)} sub={`Management ${num(k.days_project_management)} · Delivery ${num(k.days_delivery)}`} />
        <Kpi label="Fee media minima" value={money(k.fee_media_min)} sub="Prezzo minimo / giornate" />
        <Kpi label="Settimane" value={num(k.weeks)} sub={`Con contingency ${num(k.weeks_with_contingency)}`} />
        {k.signed_price !== null && k.signed_price !== undefined && (
          <>
            <Kpi wide label="Prezzo firmato" value={money(k.signed_price)} sub={`Fee media ${money(k.fee_media_signed)}`} />
            <Kpi wide label="Margine firmato" value={money(k.margin_signed)} sub={<>Margine <strong className="text-ink">{pct(k.margin_pct_signed)}</strong></>} />
          </>
        )}
      </section>

      <div>
        <div role="tablist" aria-label="Sezioni" className="flex gap-1 overflow-x-auto border-b border-line">
          {TABS.map((t) => (
            <button key={t.id} role="tab" id={`tab-${t.id}`} aria-selected={tab === t.id} aria-controls={`panel-${t.id}`} onClick={() => setTab(t.id)}
              className={`-mb-px whitespace-nowrap border-b-2 px-4 py-2.5 text-sm font-medium ${tab === t.id ? "border-ink text-ink" : "border-transparent text-muted hover:text-ink"}`}>
              {t.label}
            </button>
          ))}
        </div>
        <div role="tabpanel" id={`panel-${tab}`} aria-labelledby={`tab-${tab}`} className="pt-6">
          {tab === "dettaglio" && <DetailTab detail={detail} />}
          {tab === "riepilogo" && <SummaryTab detail={detail} />}
          {tab === "staffing" && <StaffingTab detail={detail} />}
          {tab === "versioni" && <VersionsTab ceId={ce.id} current={version.number} />}
          {tab === "storico" && <HistoryTab ceId={ce.id} />}
        </div>
      </div>
    </div>
  );
}

function Num({ children, bold }: { children: ReactNode; bold?: boolean }) {
  return <td className={`td text-right tnum whitespace-nowrap ${bold ? "font-semibold" : ""}`}>{children}</td>;
}

function DetailTab({ detail }: { detail: CeDetail }) {
  const calc = detail.calculation;
  const byPos = new Map(calc.lines.map((l) => [`${l.phase_index}:${l.line_index}`, l]));
  const external = new Set(detail.rates.filter((r) => r.is_external).map((r) => r.profile_id));
  if (detail.phases.length === 0) return <EmptyState title="Nessuna fase">Questo conto economico non ha ancora fasi.</EmptyState>;
  return (
    <div className="space-y-6">
      {detail.phases.map((phase, p) => {
        const pc = calc.phases[p];
        return (
          <div key={phase.id} role="group" className="card overflow-hidden" aria-label={`Fase ${phase.name}`}>
            <header className="flex flex-wrap items-center justify-between gap-2 border-b border-line bg-surface/60 px-4 py-3">
              <h3 className="text-base font-medium tracking-normal">{phase.name}</h3>
              <div className="flex items-center gap-2 text-xs text-muted tnum">
                {Number(phase.contingency_pct) > 0 && <Chip tone="cyan">Contingency {points(phase.contingency_pct)}</Chip>}
                <span>{num(pc.days)} giornate</span>
              </div>
            </header>
            {phase.lines.length === 0 ? (
              <p className="px-4 py-5 text-sm text-muted">Nessuna riga in questa fase.</p>
            ) : (
              <ScrollArea label={`Righe della fase ${phase.name}`}>
                <table className="w-full min-w-[46rem] border-collapse">
                  <thead className="border-b border-line"><tr>
                    <th className="th">Attività</th><th className="th">Profilo</th><th className="th">Collaboratore</th>
                    <th className="th text-right">Ore</th><th className="th text-right">Giorni</th>
                    <th className="th text-right">Ricavo</th><th className="th text-right">Costo</th><th className="th text-right">Margine</th>
                  </tr></thead>
                  <tbody className="divide-y divide-line">
                    {phase.lines.map((line, l) => {
                      const c = byPos.get(`${p}:${l}`);
                      return (
                        <tr key={line.id}>
                          <td className="td">{line.activity}{line.is_project_management && <span className="ml-2 align-middle"><Chip>PM</Chip></span>}</td>
                          <td className="td whitespace-nowrap">{line.profile_name}{external.has(line.profile_id) && <span className="ml-2 align-middle"><Chip>esterno</Chip></span>}</td>
                          <td className="td whitespace-nowrap text-muted">{line.employee_name ?? "—"}</td>
                          <Num>{num(c?.hours)}</Num><Num>{num(c?.days)}</Num>
                          <Num>{money(c?.revenue)}</Num><Num>{money(c?.cost)}</Num><Num>{money(c?.margin)}</Num>
                        </tr>
                      );
                    })}
                  </tbody>
                  <tfoot className="border-t border-ink/20 bg-surface/60">
                    <tr>
                      <td className="td font-semibold" colSpan={3}>Totale {phase.name}</td>
                      <Num bold>{num(pc.hours)}</Num><Num bold>{num(pc.days)}</Num>
                      <Num bold>{money(pc.revenue)}</Num><Num bold>{money(pc.cost)}</Num><Num bold>{money(Number(pc.revenue) - Number(pc.cost))}</Num>
                    </tr>
                    {Number(pc.contingency_revenue) > 0 && (
                      <tr><td className="td text-muted" colSpan={5}>Ricavo da contingency (senza costi)</td><Num>{money(pc.contingency_revenue)}</Num><td className="td" colSpan={2} /></tr>
                    )}
                  </tfoot>
                </table>
              </ScrollArea>
            )}
          </div>
        );
      })}
    </div>
  );
}

function SummaryTab({ detail }: { detail: CeDetail }) {
  const c = detail.calculation;
  const rows = [["Servizi interni", c.internal], ["Servizi esterni", c.external], ["Contingency", c.contingency]] as const;
  return (
    <div className="space-y-6">
      <ScrollArea label="Ricavi e costi" className="card">
        <table className="w-full min-w-[40rem] border-collapse">
          <thead className="border-b border-line bg-surface/60"><tr>
            <th className="th">Voce</th><th className="th text-right">Ricavi</th><th className="th text-right">Costi</th>
            <th className="th text-right">Margine</th><th className="th text-right">Margine %</th><th className="th text-right">C/R</th><th className="th text-right">Giornate</th>
          </tr></thead>
          <tbody className="divide-y divide-line">
            {rows.map(([label, b]) => (
              <tr key={label}><td className="td">{label}</td><Num>{money(b.revenue)}</Num><Num>{money(b.cost)}</Num><Num>{money(b.margin)}</Num><Num>{pct(b.margin_pct)}</Num><Num>{pct(b.cost_ratio)}</Num><Num>{num(b.days)}</Num></tr>
            ))}
          </tbody>
          <tfoot className="border-t border-ink/20 bg-surface/60"><tr>
            <td className="td font-semibold">Totale</td><Num bold>{money(c.total.revenue)}</Num><Num bold>{money(c.total.cost)}</Num><Num bold>{money(c.total.margin)}</Num><Num bold>{pct(c.total.margin_pct)}</Num><Num bold>{pct(c.total.cost_ratio)}</Num><Num bold>{num(c.total.days)}</Num>
          </tr></tfoot>
        </table>
      </ScrollArea>
      <ScrollArea label="Riepilogo per profilo" className="card">
        <table className="w-full min-w-[40rem] border-collapse">
          <thead className="border-b border-line bg-surface/60"><tr>
            <th className="th">Profilo</th><th className="th text-right">Ore</th><th className="th text-right">Giorni</th><th className="th text-right">Quota ore</th>
            <th className="th text-right">Ricavi</th><th className="th text-right">Costi</th><th className="th text-right">Margine</th>
          </tr></thead>
          <tbody className="divide-y divide-line">
            {c.profiles.map((p) => (
              <tr key={p.profile_id}><td className="td">{p.profile_name}{p.is_external && <span className="ml-2 align-middle"><Chip>esterno</Chip></span>}</td><Num>{num(p.hours)}</Num><Num>{num(p.days)}</Num><Num>{pct(p.hours_share)}</Num><Num>{money(p.revenue)}</Num><Num>{money(p.cost)}</Num><Num>{money(p.margin)}</Num></tr>
            ))}
            {c.profiles.length === 0 && <tr><td className="td text-muted" colSpan={7}>Nessun profilo utilizzato.</td></tr>}
          </tbody>
        </table>
      </ScrollArea>
    </div>
  );
}

function StaffingTab({ detail }: { detail: CeDetail }) {
  const monthly = detail.calculation.monthly;
  const max = Math.max(1, ...monthly.map((m) => Number(m.fte ?? 0)));
  return (
    <ScrollArea label="Staffing mensile" className="card">
      <table className="w-full min-w-[44rem] border-collapse">
        <thead className="border-b border-line bg-surface/60"><tr>
          <th className="th">Mese</th><th className="th text-right">Giorni lavorativi</th><th className="th text-right">Giorni</th><th className="th text-right">Ore</th>
          <th className="th">FTE</th><th className="th text-right">Ricavi</th><th className="th text-right">Costi</th>
        </tr></thead>
        <tbody className="divide-y divide-line">
          {monthly.map((m) => (
            <tr key={m.month}>
              <td className="td whitespace-nowrap font-medium">{month(m.month)}</td><Num>{m.work_days}</Num><Num>{num(m.days)}</Num><Num>{num(m.hours)}</Num>
              <td className="td w-56">
                <div className="flex items-center gap-3">
                  <div className="h-2 flex-1 rounded-full bg-surface" aria-hidden><div className="h-2 rounded-full bg-teal" style={{ width: `${(Number(m.fte ?? 0) / max) * 100}%` }} /></div>
                  <span className="w-16 text-right text-sm tnum">{pct(m.fte, 0)}</span>
                </div>
              </td>
              <Num>{money(m.revenue)}</Num><Num>{money(m.cost)}</Num>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="border-t border-line px-4 py-3 text-xs text-muted">Ricavi e costi mensili escludono la contingency. FTE = giorni ÷ giorni lavorativi del mese.</p>
    </ScrollArea>
  );
}

function VersionsTab({ ceId, current }: { ceId: string; current: number }) {
  const q = useQuery({ queryKey: ["ce-versions", ceId], queryFn: async () => unwrap(await api.GET("/api/v1/ce/{ce_id}/versions", { params: { path: { ce_id: ceId } } })) });
  if (q.isPending) return <Spinner label="Caricamento versioni…" />;
  if (q.isError) return <ErrorBox message={errorMessage(q.error)} onRetry={() => q.refetch()} />;
  return (
    <ul className="card divide-y divide-line">
      {q.data.map((v) => (
        <li key={v.number} className="flex flex-wrap items-center justify-between gap-3 px-4 py-3">
          <div className="flex items-center gap-3">
            <Link to={`/ce/${ceId}?v=${v.number}`} className="font-medium underline decoration-cyan decoration-2 underline-offset-4 hover:bg-cyan">Versione {v.number}</Link>
            <StatusBadge status={v.status} />
            {v.number === current && <Chip tone="cyan">in visualizzazione</Chip>}
          </div>
          <div className="text-sm text-muted tnum">{money(v.price)} · {v.created_by.full_name} · {datetime(v.updated_at)}</div>
        </li>
      ))}
    </ul>
  );
}

function HistoryTab({ ceId }: { ceId: string }) {
  const q = useQuery({ queryKey: ["ce-history", ceId], queryFn: async () => unwrap(await api.GET("/api/v1/ce/{ce_id}/history", { params: { path: { ce_id: ceId } } })) });
  if (q.isPending) return <Spinner label="Caricamento storico…" />;
  if (q.isError) return <ErrorBox message={errorMessage(q.error)} onRetry={() => q.refetch()} />;
  if (q.data.length === 0) return <EmptyState title="Nessuna attività registrata" />;
  return (
    <ol className="card divide-y divide-line">
      {q.data.map((h) => (
        <li key={h.id} className="flex flex-wrap items-baseline justify-between gap-2 px-4 py-3">
          <span><span className="mr-2 inline-block h-2 w-2 rounded-full bg-teal" aria-hidden /><span className="font-medium">{HISTORY_LABEL[h.action] ?? h.action}</span>{h.user && <span className="text-muted"> · {h.user.full_name}</span>}</span>
          <time className="text-sm text-muted tnum" dateTime={h.occurred_at}>{datetime(h.occurred_at)}</time>
        </li>
      ))}
    </ol>
  );
}

// ======================================================================= vista ridotta (viewer)
function ViewerView({ ce }: { ce: ViewerCe }) {
  const exp = useExport();
  const base = `/api/v1/ce/summaries/${ce.ce_id}/export`;
  return (
    <div className="space-y-6">
      <BackLink />
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="flex flex-wrap items-center gap-3">
            <h1 className="break-words text-3xl font-light sm:text-5xl">{ce.code}</h1>
            <StatusBadge status="approved" /><Chip>v{ce.version_number}</Chip>
          </div>
          <p className="mt-2 text-base sm:text-lg">{ce.client_name} <span className="text-muted">·</span> {ce.project_name}</p>
          <p className="mt-1 text-sm text-muted tnum">{period(ce.start_date, ce.end_date)} · approvato il {date(ce.approved_at)}</p>
        </div>
        <Menu variant="accent" label="Esporta" loading={exp.busy} items={[
          { label: "PDF", onSelect: () => exp.run(base, { format: "pdf" }) },
          { label: "Excel", onSelect: () => exp.run(base, { format: "xlsx" }) },
          { label: "CSV", onSelect: () => exp.run(base, { format: "csv" }) },
        ]} />
      </div>
      <Feedback exp={exp} />
      <section aria-label="Giornate">
        <h2 className="label">Giornate</h2>
        <div className="grid grid-cols-3 gap-3">
          <Kpi compact label="Management" value={num(ce.days_project_management)} />
          <Kpi compact label="Delivery" value={num(ce.days_delivery)} />
          <Kpi compact label="Totale" value={num(ce.days_total)} />
        </div>
      </section>
      <section aria-label="Ricavi per fase" className="card overflow-hidden">
        <table className="w-full border-collapse">
          <thead className="border-b border-line bg-surface/60"><tr><th className="th">Fase</th><th className="th text-right">Ricavi</th></tr></thead>
          <tbody className="divide-y divide-line">
            {ce.phases.map((p) => <tr key={p.name}><td className="td">{p.name}</td><Num>{money(p.revenue)}</Num></tr>)}
          </tbody>
          <tfoot className="border-t border-ink/20"><tr>
            <td className="td text-base font-semibold">Totale generale</td>
            <td className="td text-right text-xl tnum"><span className="hl">{money(ce.total_revenue)}</span></td>
          </tr></tfoot>
        </table>
      </section>
    </div>
  );
}
