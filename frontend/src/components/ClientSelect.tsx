import { useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";

import { api, unwrap } from "../api/client";
import { useClients } from "../api/lookups";
import { errorMessage } from "../lib/errors";
import { Button } from "./ui/Button";
import { ErrorBox } from "./ui/Feedback";
import { Modal } from "./ui/Modal";

/** Scelta del cliente, con la possibilità di crearne uno nuovo senza lasciare la pagina. */
export function ClientSelect({ id, value, onChange, invalid }: { id: string; value: string; onChange: (id: string) => void; invalid?: boolean }) {
  const clients = useClients();
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function create(e: FormEvent) {
    e.preventDefault();
    e.stopPropagation(); // questo modulo sta dentro un altro: il suo invio non deve far partire quello esterno
    setBusy(true);
    setError(null);
    try {
      const created = unwrap(await api.POST("/api/v1/clients", { body: { name: name.trim() } }));
      await qc.invalidateQueries({ queryKey: ["clients-lookup"] });
      onChange(created.id);
      setOpen(false);
      setName("");
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex gap-2">
      <select id={id} className={`field ${invalid ? "border-red-600" : ""}`} value={value} onChange={(e) => onChange(e.target.value)} aria-invalid={invalid || undefined}>
        <option value="">Scegli il cliente…</option>
        {clients.data?.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
      </select>
      <Button type="button" variant="secondary" size="sm" className="shrink-0" onClick={() => setOpen(true)}>+ Nuovo</Button>
      <Modal open={open} title="Nuovo cliente" onClose={() => setOpen(false)}>
        <form onSubmit={create} className="space-y-4">
          {error && <ErrorBox message={error} />}
          <div><label htmlFor={`${id}-new`} className="label">Nome del cliente</label><input id={`${id}-new`} className="field" value={name} onChange={(e) => setName(e.target.value)} required maxLength={300} autoFocus /></div>
          <div className="flex justify-end gap-2">
            <Button type="button" variant="ghost" onClick={() => setOpen(false)}>Annulla</Button>
            <Button type="submit" loading={busy} disabled={!name.trim()}>Crea cliente</Button>
          </div>
        </form>
      </Modal>
    </div>
  );
}
