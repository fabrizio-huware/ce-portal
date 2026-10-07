import { Button } from "./Button";

type Props = { total: number; limit: number; offset: number; onChange: (offset: number) => void };

export function Pagination({ total, limit, offset, onChange }: Props) {
  if (total <= limit) return null;
  const page = Math.floor(offset / limit) + 1;
  const pages = Math.ceil(total / limit);
  return (
    <nav aria-label="Paginazione" className="flex items-center justify-between gap-3 pt-4">
      <p className="text-sm text-muted tnum">Pagina {page} di {pages}</p>
      <div className="flex gap-2">
        <Button variant="secondary" size="sm" disabled={page <= 1} onClick={() => onChange(offset - limit)}>← Precedente</Button>
        <Button variant="secondary" size="sm" disabled={page >= pages} onClick={() => onChange(offset + limit)}>Successiva →</Button>
      </div>
    </nav>
  );
}
