import { useEffect, useRef, useState, type ReactNode } from "react";

import { Button } from "./Button";

export type MenuItem = { label: string; onSelect: () => void; hint?: string } | "separator";

/** Menu a tendina accessibile: si chiude con Esc o cliccando fuori. */
export function Menu({ label, items, variant = "secondary", loading }: { label: ReactNode; items: MenuItem[]; variant?: "secondary" | "primary" | "accent"; loading?: boolean }) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => !ref.current?.contains(e.target as Node) && setOpen(false);
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);
  return (
    <div ref={ref} className="relative">
      <Button variant={variant} size="sm" aria-haspopup="menu" aria-expanded={open} loading={loading} onClick={() => setOpen((o) => !o)}>
        {label} <span aria-hidden className="text-xs">▾</span>
      </Button>
      {open && (
        <div role="menu" className="absolute right-0 z-30 mt-2 min-w-[15rem] overflow-hidden rounded-xl border border-line bg-paper py-1 shadow-lg">
          {items.map((item, i) =>
            item === "separator" ? (
              <div key={i} role="separator" className="my-1 border-t border-line" />
            ) : (
              <button key={item.label} role="menuitem" className="block w-full px-4 py-2 text-left text-sm hover:bg-surface focus-visible:bg-surface"
                onClick={() => { setOpen(false); item.onSelect(); }}>
                {item.label}
                {item.hint && <span className="block text-xs text-muted">{item.hint}</span>}
              </button>
            ),
          )}
        </div>
      )}
    </div>
  );
}
