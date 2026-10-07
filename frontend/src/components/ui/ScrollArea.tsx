import type { ReactNode } from "react";

/** Contenitore scorrevole in orizzontale, raggiungibile e scorribile anche con la tastiera. */
export function ScrollArea({ label, children, className = "" }: { label: string; children: ReactNode; className?: string }) {
  return (
    <div className={className}>
      <div role="region" aria-label={label} tabIndex={0} className="overflow-x-auto">
        {children}
      </div>
      <p className="px-3 pb-2 pt-1 text-[11px] text-muted md:hidden" aria-hidden>Scorri di lato per vedere tutte le colonne →</p>
    </div>
  );
}
