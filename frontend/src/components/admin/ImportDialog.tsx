import { useState, type ReactNode } from "react";

import { uploadCsv, type ImportResult } from "../../api/upload";
import { errorMessage } from "../../lib/errors";
import { Button } from "../ui/Button";
import { ErrorBox, Notice } from "../ui/Feedback";
import { Modal } from "../ui/Modal";

type Props = {
  open: boolean;
  onClose: () => void;
  title: string;
  path: string;
  /** Descrizione delle colonne attese. */
  columns: ReactNode;
  /** File di esempio da scaricare (in /public). */
  example: string;
  /** Spiega cosa fa l'importazione. */
  note?: ReactNode;
  onDone: () => void;
};

const PLURAL = (n: number, one: string, many: string) => `${n} ${n === 1 ? one : many}`;

/**
 * Importazione CSV in due fasi: prima si controlla il file (nulla viene scritto), poi si conferma.
 * Se anche una sola riga è errata non si importa nulla e gli errori sono elencati per riga.
 */
export function ImportDialog({ open, onClose, title, path, columns, example, note, onDone }: Props) {
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<ImportResult | null>(null);
  const [applied, setApplied] = useState<ImportResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const reset = () => { setFile(null); setPreview(null); setApplied(null); setError(null); };
  const close = () => { reset(); onClose(); };

  async function run(dryRun: boolean) {
    if (!file) return;
    setBusy(true);
    setError(null);
    try {
      const result = await uploadCsv(path, file, dryRun);
      if (dryRun) setPreview(result);
      else if (result.errors.length === 0) { setApplied(result); onDone(); }
      else setPreview(result);
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }

  const ok = preview !== null && preview.errors.length === 0 && preview.total_rows > 0;
  const nothingToChange = ok && preview!.created + preview!.updated === 0;
  return (
    <Modal open={open} title={title} onClose={close} wide
      footer={applied ? <Button onClick={close}>Chiudi</Button> : (
        <>
          <Button variant="ghost" onClick={close}>Annulla</Button>
          {!ok ? <Button loading={busy} disabled={!file} onClick={() => void run(true)}>Controlla il file</Button>
            : <Button variant="accent" loading={busy} disabled={nothingToChange} onClick={() => void run(false)}>Importa</Button>}
        </>
      )}>
      {applied ? (
        <Notice tone="ok">
          <strong>Importazione completata.</strong> {PLURAL(applied.created, "creato", "creati")}, {PLURAL(applied.updated, "aggiornato", "aggiornati")}, {applied.unchanged} invariati.
          {Object.entries(applied.extra ?? {}).map(([k, v]) => <span key={k}> · {k.replace(/_/g, " ")}: {v}</span>)}
        </Notice>
      ) : (
        <>
          <div className="space-y-1 text-muted">
            <p>File CSV con le colonne: {columns}. Separatore «;», codifica UTF-8, al massimo 5000 righe.</p>
            {note && <p>{note}</p>}
            <p><a className="font-medium text-teal-700 underline underline-offset-4" href={example} download>Scarica un file di esempio</a></p>
          </div>
          <div>
            <label htmlFor="csv-file" className="label">File CSV</label>
            <input id="csv-file" type="file" accept=".csv,text/csv" className="field" onChange={(e) => { setFile(e.target.files?.[0] ?? null); setPreview(null); setError(null); }} />
          </div>
          {error && <ErrorBox message={error} />}
          {preview && preview.errors.length > 0 && (
            <div role="alert" className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-red-900">
              <p className="font-medium">Il file contiene {PLURAL(preview.errors.length, "errore", "errori")}: non è stato importato nulla.</p>
              <ul className="mt-2 max-h-48 list-disc space-y-1 overflow-y-auto pl-5">
                {preview.errors.map((e, i) => <li key={i}>{e.line ? `Riga ${e.line}: ` : ""}{e.message}</li>)}
              </ul>
              <p className="mt-2 text-sm">Correggi il file e ricontrollalo.</p>
            </div>
          )}
          {preview && preview.errors.length === 0 && (
            <div role="status" className="rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-emerald-900">
              <p className="font-medium">Il file è corretto: {PLURAL(preview.total_rows, "riga", "righe")}.</p>
              <p className="mt-1">{PLURAL(preview.created, "nuovo", "nuovi")} · {PLURAL(preview.updated, "da aggiornare", "da aggiornare")} · {preview.unchanged} invariati.
                {Object.entries(preview.extra ?? {}).map(([k, v]) => <span key={k}> · {k.replace(/_/g, " ")}: {v}</span>)}</p>
              <p className="mt-1 text-sm">{nothingToChange ? "Non c'è nulla da cambiare." : "Nulla è ancora stato scritto: premi «Importa» per confermare."}</p>
            </div>
          )}
        </>
      )}
    </Modal>
  );
}
