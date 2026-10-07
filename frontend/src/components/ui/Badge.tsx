import { STATUS, type CeStatus } from "../../lib/status";

export function StatusBadge({ status }: { status: string }) {
  const s = STATUS[status as CeStatus] ?? STATUS.draft;
  return (
    <span className={`inline-flex items-center gap-1.5 whitespace-nowrap rounded-full border px-2.5 py-0.5 text-xs font-medium ${s.classes}`}>
      <span className={`h-1.5 w-1.5 rounded-full ${s.dot}`} aria-hidden />
      {s.label}
    </span>
  );
}

export function Chip({ children, tone = "neutral" }: { children: React.ReactNode; tone?: "neutral" | "cyan" }) {
  const tones = { neutral: "bg-surface text-ink border-line", cyan: "bg-cyan-100 text-ink border-cyan-200" };
  return <span className={`inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-medium ${tones[tone]}`}>{children}</span>;
}
