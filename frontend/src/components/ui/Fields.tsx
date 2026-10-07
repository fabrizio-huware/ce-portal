import type { InputHTMLAttributes, ReactNode, SelectHTMLAttributes, TextareaHTMLAttributes } from "react";

type Base = { id: string; label: string; hint?: ReactNode; error?: string | null; className?: string };

export function TextField({ id, label, hint, error, className = "", ...rest }: Base & InputHTMLAttributes<HTMLInputElement>) {
  return (
    <div className={className}>
      <label htmlFor={id} className="label">{label}</label>
      <input id={id} className={`field ${error ? "border-red-600" : ""}`} aria-invalid={error ? true : undefined} aria-describedby={hint || error ? `${id}-d` : undefined} {...rest} />
      {(hint || error) && <p id={`${id}-d`} className={`mt-1 text-xs ${error ? "text-red-700" : "text-muted"}`}>{error ?? hint}</p>}
    </div>
  );
}

export function TextAreaField({ id, label, hint, className = "", ...rest }: Base & TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return (
    <div className={className}>
      <label htmlFor={id} className="label">{label}</label>
      <textarea id={id} className="field min-h-20" aria-describedby={hint ? `${id}-d` : undefined} {...rest} />
      {hint && <p id={`${id}-d`} className="mt-1 text-xs text-muted">{hint}</p>}
    </div>
  );
}

export function SelectField({ id, label, hint, className = "", children, ...rest }: Base & SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <div className={className}>
      <label htmlFor={id} className="label">{label}</label>
      <select id={id} className="field" aria-describedby={hint ? `${id}-d` : undefined} {...rest}>{children}</select>
      {hint && <p id={`${id}-d`} className="mt-1 text-xs text-muted">{hint}</p>}
    </div>
  );
}

export function CheckField({ id, label, hint, ...rest }: Omit<Base, "error" | "className"> & InputHTMLAttributes<HTMLInputElement>) {
  return (
    <div>
      <label htmlFor={id} className="flex items-center gap-2 text-sm"><input id={id} type="checkbox" className="h-4 w-4 accent-ink" {...rest} /> {label}</label>
      {hint && <p className="ml-6 mt-1 text-xs text-muted">{hint}</p>}
    </div>
  );
}
