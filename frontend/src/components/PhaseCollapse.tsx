import type { Calculation } from "../api/types";
import { money, num } from "../lib/format";
import { Button } from "./ui/Button";

type PhaseCalc = Calculation["phases"][number];

/** Freccia che chiude o apre una fase: sul telefono e con la tastiera è un vero pulsante. */
export function CollapseButton({ open, onClick, name }: { open: boolean; onClick: () => void; name: string }) {
  return (
    <button type="button" onClick={onClick} aria-expanded={open} aria-label={`${open ? "Comprimi" : "Espandi"} ${name}`}
      className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border-2 border-ink bg-paper">
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden
        className={`transition-transform ${open ? "rotate-90" : ""}`}><path d="M5 3 L11 8 L5 13" /></svg>
    </button>
  );
}

/** «Comprimi tutte» e «Espandi tutte»: compaiono solo se c'è più di una fase. */
export function CollapseAll({ count, onCollapse, onExpand }: { count: number; onCollapse: () => void; onExpand: () => void }) {
  if (count < 2) return null;
  return (
    <div className="flex gap-2">
      <Button variant="secondary" size="sm" onClick={onCollapse}>Comprimi tutte</Button>
      <Button variant="secondary" size="sm" onClick={onExpand}>Espandi tutte</Button>
    </div>
  );
}

function Cell({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="text-right">
      <dt className="text-[11px] font-medium uppercase tracking-wide text-muted">{label}</dt>
      <dd className="tnum text-base font-medium">{value}</dd>
      {sub && <dd className="tnum whitespace-nowrap text-xs font-medium text-teal-700">{sub}</dd>}
    </div>
  );
}

/** Totali di una fase chiusa: ore, giorni, ricavo e costo, con giorni e ricavo comprensivi di contingency. */
export function PhaseTotals({ pc, stale }: { pc: PhaseCalc; stale?: boolean }) {
  const cont = Number(pc.contingency_pct) > 0;
  return (
    <dl aria-label="Totali della fase" className={`flex flex-wrap justify-end gap-x-6 gap-y-2 ${stale ? "opacity-50" : ""}`}>
      <Cell label="Ore" value={num(pc.hours)} />
      <Cell label="Giorni" value={num(pc.days)} sub={cont ? `con cont. ${num(pc.days_with_contingency)}` : undefined} />
      <Cell label="Ricavo" value={money(pc.revenue)} sub={cont ? `con cont. ${money(pc.revenue_with_contingency)}` : undefined} />
      <Cell label="Costo" value={money(pc.cost)} />
    </dl>
  );
}
