import { useState, type ReactNode } from "react";

import { Button } from "./ui/Button";

/** Riquadro dei filtri: da computer sempre aperto, su smartphone dietro il pulsante «Filtri». */
export function FilterPanel({ active, columns, children }: { active: number; columns: string; children: ReactNode }) {
  const [open, setOpen] = useState(false);
  return (
    <section aria-label="Filtri" className="card mb-6 p-4">
      <div className="md:hidden">
        <Button variant="secondary" size="sm" aria-expanded={open} onClick={() => setOpen((o) => !o)}>
          Filtri{active > 0 && <span className="rounded-full bg-cyan px-1.5 text-xs">{active}</span>}
        </Button>
      </div>
      <div className={`${open ? "mt-4 grid" : "hidden"} grid-cols-1 gap-4 sm:grid-cols-2 md:mt-0 md:grid ${columns}`}>{children}</div>
    </section>
  );
}
