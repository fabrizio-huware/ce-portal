import { useState } from "react";

import { api } from "../api/client";
import { ApiError, errorDetails } from "../lib/errors";
import { Button } from "./ui/Button";
import { TextAreaField, TextField } from "./ui/Fields";
import { ErrorBox, Notice } from "./ui/Feedback";
import { Modal } from "./ui/Modal";

type Choice = { id: string; label: string; hint?: string; format: "pdf" | "xlsx"; variant: "summary" | "full" };

// Il riepilogo è il formato consigliato: non contiene costi né margini e si può mandare all'esterno.
export const REPORT_CHOICES: Choice[] = [
  { id: "summary-pdf", label: "Riepilogo PDF", hint: "Senza costi né righe: si può condividere", format: "pdf", variant: "summary" },
  { id: "summary-xlsx", label: "Riepilogo Excel", format: "xlsx", variant: "summary" },
  { id: "full-pdf", label: "PDF completo", hint: "Uso interno · contiene costi e margini", format: "pdf", variant: "full" },
  { id: "full-xlsx", label: "Excel completo", hint: "Con formule modificabili · contiene costi e margini", format: "xlsx", variant: "full" },
];

type Sent = { recipient: string; filename: string; status: "sent" | "queued" | "failed"; error?: string | null };

const MAX_MESSAGE = 500;

/** Invio del report di un CE per email: scelta del file, indirizzo e messaggio facoltativo. */
export function SendReportDialog({ open, onClose, ceId, version }: { open: boolean; onClose: () => void; ceId: string; version?: string }) {
  const [choiceId, setChoiceId] = useState("summary-pdf");
  const [recipient, setRecipient] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<{ message: string; status?: number } | null>(null);
  const [sent, setSent] = useState<Sent | null>(null);
  const choice = REPORT_CHOICES.find((c) => c.id === choiceId)!;
  const valid = /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(recipient.trim());

  function close() {
    onClose();
    setSent(null); setError(null); setMessage(""); setChoiceId("summary-pdf"); setRecipient("");
  }

  async function send() {
    setError(null); setBusy(true);
    try {
      const result = await api.POST("/api/v1/ce/{ce_id}/export/email", {
        params: { path: { ce_id: ceId } },
        body: { recipient: recipient.trim(), format: choice.format, variant: choice.variant, version: version ? Number(version) : null, message: message.trim() || null },
      });
      if (result.error !== undefined || !result.data) throw new ApiError(result.response.status, result.error);
      setSent(result.data);
    } catch (e) {
      const d = errorDetails(e);
      setError({ message: d.message, status: d.status });
    } finally {
      setBusy(false);
    }
  }

  const footer = sent ? (
    <Button onClick={close}>Chiudi</Button>
  ) : (
    <>
      <Button variant="secondary" onClick={close} disabled={busy}>Annulla</Button>
      <Button variant="accent" onClick={send} loading={busy} disabled={!valid}>Invia</Button>
    </>
  );

  return (
    <Modal open={open} title={sent ? "Report inviato" : "Invia il report per email"} onClose={close} footer={footer}>
      {sent ? (
        <>
          {sent.status === "sent" && <Notice tone="ok"><strong>{sent.filename}</strong> è stato inviato a <strong>{sent.recipient}</strong>.</Notice>}
          {sent.status === "queued" && <Notice tone="warn">Il server di posta non ha risposto: l'email di <strong>{sent.recipient}</strong> è in coda e il portale riprova da solo.</Notice>}
          {sent.status === "failed" && <ErrorBox message={`L'invio a ${sent.recipient} è stato rifiutato${sent.error ? `: ${sent.error}` : ""}. Un amministratore può riprovarlo dalle notifiche.`} />}
          <p className="text-xs text-muted">Ogni invio resta nel registro delle attività: chi, quando, a quale indirizzo e quale formato.</p>
        </>
      ) : (
        <>
          <fieldset className="space-y-2">
            <legend className="label">Che cosa vuoi inviare</legend>
            {REPORT_CHOICES.map((c) => (
              <label key={c.id} className={`flex cursor-pointer items-center gap-3 rounded-xl border px-3 py-2 ${choiceId === c.id ? "border-teal bg-cyan-100/60" : "border-line"}`}>
                <input type="radio" name="report-choice" className="h-4 w-4 accent-ink" checked={choiceId === c.id} onChange={() => setChoiceId(c.id)} />
                <span className="flex-1"><span className="font-medium">{c.label}</span>{c.hint && <span className="block text-xs text-muted">{c.hint}</span>}</span>
                {c.id === "summary-pdf" && <span className="rounded-full bg-ink px-2 py-0.5 text-[0.65rem] font-bold uppercase tracking-wide text-cyan">Consigliato</span>}
              </label>
            ))}
          </fieldset>
          {choice.variant === "full" && (
            <Notice tone="warn">Il report completo contiene costi e margini: si può inviare solo a indirizzi aziendali. Per un destinatario esterno scegli un riepilogo.</Notice>
          )}
          <TextField id="report-to" label="Indirizzo del destinatario" type="email" autoComplete="off" value={recipient} onChange={(e) => setRecipient(e.target.value)}
            hint="Un solo indirizzo. Per più destinatari ripeti l'invio." />
          <TextAreaField id="report-msg" label="Messaggio (facoltativo)" rows={2} maxLength={MAX_MESSAGE} value={message} onChange={(e) => setMessage(e.target.value)} hint={`${message.length}/${MAX_MESSAGE}`} />
          {error && (
            <div className="space-y-2">
              <ErrorBox message={error.message} />
              {error.status === 403 && choice.variant === "full" && (
                <Button variant="secondary" size="sm" onClick={() => { setChoiceId(choice.format === "xlsx" ? "summary-xlsx" : "summary-pdf"); setError(null); }}>Passa al riepilogo</Button>
              )}
            </div>
          )}
        </>
      )}
    </Modal>
  );
}
