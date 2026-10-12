/** Scelta fra poche alternative sempre visibili (come una fila di pulsanti collegati). */
export function Segmented<T extends string>({ label, value, options, onChange }: { label: string; value: T; options: { value: T; label: string }[]; onChange: (value: T) => void }) {
  return (
    <div role="group" aria-label={label} className="inline-flex overflow-hidden rounded-lg border border-ink">
      {options.map((o) => {
        const active = o.value === value;
        return (
          <button key={o.value} type="button" aria-pressed={active} onClick={() => onChange(o.value)}
            className={`border-l border-ink/30 px-3 py-1.5 text-sm font-medium first:border-l-0 ${active ? "bg-ink text-paper" : "bg-paper hover:bg-surface"}`}>
            {o.label}
          </button>
        );
      })}
    </div>
  );
}
