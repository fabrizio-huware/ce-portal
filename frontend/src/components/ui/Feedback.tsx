import type { ReactNode } from "react";

export function EmptyState({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="card grid place-items-center px-6 py-14 text-center">
      <div className="mb-3 h-1.5 w-12 rounded-full bg-cyan" aria-hidden />
      <h3 className="text-lg font-medium">{title}</h3>
      {children && <p className="mt-1 max-w-md text-sm text-muted">{children}</p>}
    </div>
  );
}

export function ErrorBox({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div role="alert" className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-900">
      <span>{message}</span>
      {onRetry && <button onClick={onRetry} className="font-medium underline underline-offset-2">Riprova</button>}
    </div>
  );
}

export function Notice({ children, tone = "info" }: { children: ReactNode; tone?: "info" | "ok" }) {
  const tones = { info: "border-cyan-200 bg-cyan-100/60", ok: "border-emerald-200 bg-emerald-50 text-emerald-900" };
  return <div role="status" className={`rounded-xl border px-4 py-3 text-sm ${tones[tone]}`}>{children}</div>;
}
