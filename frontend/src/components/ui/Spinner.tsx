export function Spinner({ label }: { label?: string }) {
  return (
    <div role="status" className="inline-flex items-center gap-2.5 text-sm text-muted">
      <svg className="h-5 w-5 animate-spin" viewBox="0 0 24 24" fill="none" aria-hidden>
        <circle cx="12" cy="12" r="9" stroke="currentColor" strokeOpacity=".2" strokeWidth="3" />
        <path d="M21 12a9 9 0 0 0-9-9" stroke="#00acc7" strokeWidth="3" strokeLinecap="round" />
      </svg>
      {label ? <span>{label}</span> : <span className="sr-only">Caricamento…</span>}
    </div>
  );
}
