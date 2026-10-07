import type { ReactNode } from "react";

/** Indicatore di una dashboard: etichetta, valore grande e una riga di contesto. */
export function Stat({ label, value, sub, highlight }: { label: string; value: ReactNode; sub?: ReactNode; highlight?: boolean }) {
  return (
    <div className="card p-4">
      <div className="label !mb-2">{label}</div>
      <div className="whitespace-nowrap text-2xl font-light tracking-tightest tnum sm:text-[1.7rem]">{highlight ? <span className="hl">{value}</span> : value}</div>
      {sub && <div className="mt-1.5 text-xs text-muted tnum">{sub}</div>}
    </div>
  );
}
