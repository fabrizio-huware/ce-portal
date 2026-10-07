import type { Calculation } from "../api/types";
import { Spinner } from "../components/ui/Spinner";
import { money, num, pct } from "../lib/format";

export type PreviewState = "ok" | "calculating" | "incomplete" | "error";

const LABEL: Record<PreviewState, string> = {
  ok: "Calcolo aggiornato",
  calculating: "Calcolo in corso…",
  incomplete: "Completa i dati per aggiornare il calcolo",
  error: "Anteprima non disponibile",
};

/** Totali del CE mentre si modifica: li calcola il server con lo stesso motore del salvataggio. */
export function PreviewBar({ calc, state }: { calc: Calculation | undefined; state: PreviewState }) {
  const k = calc?.kpis;
  const stale = state !== "ok";
  return (
    <section aria-label="Anteprima dei totali" className="z-30 rounded-xl border border-ink bg-paper px-4 py-3 shadow-card md:sticky md:top-[4.5rem]">
      <div className={`grid grid-cols-2 gap-x-6 gap-y-2 sm:grid-cols-4 ${stale ? "opacity-60" : ""}`}>
        <Item label="Prezzo progetto" value={k ? <span className="hl">{money(k.price_project)}</span> : "—"} />
        <Item label="Margine" value={calc ? money(calc.total.margin) : "—"} sub={calc ? pct(calc.total.margin_pct) : undefined} />
        <Item label="Costi" value={calc ? money(calc.total.cost) : "—"} />
        <Item label="Giornate" value={k ? num(k.days_total) : "—"} />
      </div>
      <p aria-live="polite" className="mt-2 flex items-center gap-2 text-xs text-muted">
        {state === "calculating" ? <Spinner /> : <span className={`h-1.5 w-1.5 rounded-full ${state === "ok" ? "bg-emerald-500" : "bg-amber-500"}`} aria-hidden />}
        {LABEL[state]}
      </p>
    </section>
  );
}

function Item({ label, value, sub }: { label: string; value: React.ReactNode; sub?: string }) {
  return (
    <div className="min-w-0">
      <div className="text-[11px] font-medium uppercase tracking-wide text-muted">{label}</div>
      <div className="whitespace-nowrap text-lg font-light tracking-tightest tnum sm:text-xl">{value}</div>
      {sub && <div className="text-xs text-muted tnum">{sub}</div>}
    </div>
  );
}
