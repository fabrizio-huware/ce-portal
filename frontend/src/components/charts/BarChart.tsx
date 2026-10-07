import { useId } from "react";

import { compact, niceMax } from "../../lib/scale";
import { ScrollArea } from "../ui/ScrollArea";

export type Series = { key: string; name: string; fill: string; hatch?: boolean };
export type Datum = { label: string; values: Record<string, number> };

const INK = "#0a0a0a";
export const SERIES_APPROVED: Series = { key: "approved", name: "Approvati", fill: INK };
export const SERIES_PIPELINE: Series = { key: "pipeline", name: "Pipeline", fill: "#00f5fe", hatch: true };

const total = (d: Datum, series: Series[]) => series.reduce((s, x) => s + (d.values[x.key] ?? 0), 0);

/** Legenda: ogni serie ha colore e nome scritto (e la pipeline anche un tratteggio), così non conta solo il colore. */
export function Legend({ series }: { series: Series[] }) {
  const id = useId();
  return (
    <ul className="flex flex-wrap gap-x-5 gap-y-1 text-xs text-muted" aria-label="Legenda">
      {series.map((s) => (
        <li key={s.key} className="flex items-center gap-2">
          <svg width="16" height="12" aria-hidden>
            {s.hatch && <Hatch id={`${id}-${s.key}`} fill={s.fill} />}
            <rect x="0.75" y="0.75" width="14.5" height="10.5" rx="2" fill={s.hatch ? `url(#${id}-${s.key})` : s.fill} stroke={INK} strokeWidth="1.5" />
          </svg>
          {s.name}
        </li>
      ))}
    </ul>
  );
}

function Hatch({ id, fill }: { id: string; fill: string }) {
  return (
    <pattern id={id} patternUnits="userSpaceOnUse" width="6" height="6" patternTransform="rotate(45)">
      <rect width="6" height="6" fill={fill} />
      <line x1="0" y1="0" x2="0" y2="6" stroke={INK} strokeWidth="1.5" />
    </pattern>
  );
}

/** Tabella con gli stessi dati del grafico, visibile solo ai lettori di schermo. */
function DataTable({ title, data, series, format }: { title: string; data: Datum[]; series: Series[]; format: (n: number) => string }) {
  return (
    <table className="sr-only">
      <caption>{title}</caption>
      <thead><tr><th scope="col">Voce</th>{series.map((s) => <th key={s.key} scope="col">{s.name}</th>)}</tr></thead>
      <tbody>{data.map((d) => <tr key={d.label}><th scope="row">{d.label}</th>{series.map((s) => <td key={s.key}>{format(d.values[s.key] ?? 0)}</td>)}</tr>)}</tbody>
    </table>
  );
}

type VerticalProps = { title: string; data: Datum[]; series: Series[]; format: (n: number) => string; unit?: string };

/** Barre verticali impilate (per esempio i ricavi mese per mese). */
export function BarChart({ title, data, series, format, unit = "€" }: VerticalProps) {
  const id = useId();
  const L = 46, R = 8, T = 14, B = 30, H = 250;
  const step = 64;
  const W = Math.max(340, data.length * step + L + R);
  const max = niceMax(Math.max(0, ...data.map((d) => total(d, series))));
  const y = (v: number) => T + (H - T - B) * (1 - v / max);
  const ticks = [0, 0.25, 0.5, 0.75, 1].map((f) => f * max);
  return (
    <figure className="relative" aria-label={title}>
      <figcaption className="mb-2 text-sm font-medium">{title}</figcaption>
      <div>
        <ScrollArea label={`Grafico: ${title}`}>
          <svg viewBox={`0 0 ${W} ${H}`} width="100%" className="h-auto max-w-none" aria-hidden="true" style={{ minWidth: W }}>
            <defs>{series.filter((s) => s.hatch).map((s) => <Hatch key={s.key} id={`${id}-${s.key}`} fill={s.fill} />)}</defs>
            {ticks.map((t) => (
              <g key={t}>
                <line x1={L} x2={W - R} y1={y(t)} y2={y(t)} stroke="#e1e5e8" />
                <text x={L - 6} y={y(t) + 4} textAnchor="end" fontSize="11" fill="#5b6770">{compact(t)}{t === max ? ` ${unit}` : ""}</text>
              </g>
            ))}
            {data.map((d, i) => {
              const cx = L + (i + 0.5) * ((W - L - R) / data.length);
              const w = Math.min(38, ((W - L - R) / data.length) * 0.62);
              let acc = 0;
              return (
                <g key={d.label}>
                  {series.map((s) => {
                    const v = d.values[s.key] ?? 0;
                    if (v <= 0) return null;
                    const top = y(acc + v);
                    const h = y(acc) - top;
                    acc += v;
                    return (
                      <rect key={s.key} x={cx - w / 2} y={top} width={w} height={Math.max(h, 0.5)} fill={s.hatch ? `url(#${id}-${s.key})` : s.fill} stroke={INK} strokeWidth="1">
                        <title>{`${d.label} · ${s.name}: ${format(v)}`}</title>
                      </rect>
                    );
                  })}
                  <text x={cx} y={H - 10} textAnchor="middle" fontSize="11" fill="#0a0a0a">{d.label}</text>
                </g>
              );
            })}
          </svg>
          <DataTable title={title} data={data} series={series} format={format} />
        </ScrollArea>
      </div>
      <div className="mt-2"><Legend series={series} /></div>
    </figure>
  );
}

type HorizontalProps = { title: string; rows: Datum[]; series: Series[]; format: (n: number) => string; limit?: number };

/** Barre orizzontali impilate con il valore scritto accanto (per esempio i ricavi per cliente). */
export function HBars({ title, rows, series, format, limit = 8 }: HorizontalProps) {
  const sorted = [...rows].sort((a, b) => total(b, series) - total(a, series));
  const shown = sorted.slice(0, limit);
  const rest = sorted.slice(limit);
  const data = rest.length
    ? [...shown, { label: `Altri (${rest.length})`, values: Object.fromEntries(series.map((s) => [s.key, rest.reduce((sum, r) => sum + (r.values[s.key] ?? 0), 0)])) }]
    : shown;
  const max = Math.max(1, ...data.map((d) => total(d, series)));
  return (
    <figure className="relative" aria-label={title}>
      <figcaption className="mb-3 text-sm font-medium">{title}</figcaption>
      {data.length === 0 ? <p className="text-sm text-muted">Nessun dato nel periodo.</p> : (
        <ul className="space-y-2" aria-hidden>
          {data.map((d) => (
            <li key={d.label} className="grid grid-cols-[minmax(5rem,9rem)_1fr_auto] items-center gap-3 text-sm">
              <span className="truncate" title={d.label}>{d.label}</span>
              <span className="flex h-5 overflow-hidden rounded-sm bg-surface">
                {series.map((s) => {
                  const v = d.values[s.key] ?? 0;
                  if (v <= 0) return null;
                  return <span key={s.key} title={`${s.name}: ${format(v)}`} style={{ width: `${(v / max) * 100}%`, background: s.hatch ? `repeating-linear-gradient(45deg, ${s.fill} 0 4px, ${INK} 4px 5px)` : s.fill, borderRight: `1px solid ${INK}` }} />;
                })}
              </span>
              <span className="whitespace-nowrap text-right tnum">{format(total(d, series))}</span>
            </li>
          ))}
        </ul>
      )}
      <DataTable title={title} data={data} series={series} format={format} />
      <div className="mt-3"><Legend series={series} /></div>
    </figure>
  );
}
