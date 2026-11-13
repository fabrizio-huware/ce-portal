import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const post = vi.fn();
vi.mock("../api/client", async (orig) => ({ ...(await orig<typeof import("../api/client")>()), api: { POST: (...a: unknown[]) => post(...a) } }));

import { SendReportDialog } from "../components/SendReportDialog";

const ok = (status = "sent", extra: Record<string, unknown> = {}) => ({ data: { recipient: "mario@cliente.it", filename: "PS-1_v2_riepilogo.pdf", status, error: null, ...extra }, response: { status: 200 } });
const fail = (status: number, detail: string) => ({ error: { detail }, response: { status } });
const onClose = vi.fn();
const view = () => render(<SendReportDialog open onClose={onClose} ceId="ce-1" version="2" />);
const type = async (address: string) => userEvent.type(screen.getByLabelText("Indirizzo del destinatario"), address);
const send = () => screen.getByRole("button", { name: "Invia" });

beforeEach(() => { post.mockReset(); onClose.mockReset(); });

describe("SendReportDialog", () => {
  it("parte dal riepilogo PDF e non si invia senza un indirizzo valido", async () => {
    view();
    expect(screen.getByLabelText(/Riepilogo PDF/)).toBeChecked();
    expect(send()).toBeDisabled();
    await type("senza-chiocciola");
    expect(send()).toBeDisabled();
    await userEvent.type(screen.getByLabelText("Indirizzo del destinatario"), "@x.it");
    expect(send()).toBeEnabled();
  });
  it("invia il formato scelto, la versione e il messaggio", async () => {
    post.mockResolvedValue(ok());
    view();
    await userEvent.click(screen.getByLabelText(/Riepilogo Excel/));
    await type("  mario@cliente.it ");
    await userEvent.type(screen.getByLabelText(/Messaggio/), "Ecco il riepilogo");
    await userEvent.click(send());
    expect(post).toHaveBeenCalledWith("/api/v1/ce/{ce_id}/export/email", {
      params: { path: { ce_id: "ce-1" } },
      body: { recipient: "mario@cliente.it", format: "xlsx", variant: "summary", version: 2, message: "Ecco il riepilogo" },
    });
    expect(await screen.findByRole("status")).toHaveTextContent("PS-1_v2_riepilogo.pdf è stato inviato a mario@cliente.it");
    expect(screen.queryByRole("button", { name: "Invia" })).not.toBeInTheDocument();
  });
  it("senza messaggio non manda testo vuoto", async () => {
    post.mockResolvedValue(ok());
    view();
    await type("mario@cliente.it");
    await userEvent.click(send());
    expect(post.mock.calls[0][1].body.message).toBeNull();
  });
  it("scegliendo un report completo avvisa che contiene costi e margini", async () => {
    view();
    expect(screen.queryByText(/contiene costi e margini: si può inviare solo/)).not.toBeInTheDocument();
    await userEvent.click(screen.getByLabelText(/Excel completo/));
    expect(screen.getByRole("status")).toHaveTextContent("solo a indirizzi aziendali");
  });
  it("se il server rifiuta il completo a un esterno mostra il motivo e propone il riepilogo", async () => {
    post.mockResolvedValue(fail(403, "Il report completo contiene costi e margini: scegli un riepilogo."));
    view();
    await userEvent.click(screen.getByLabelText(/PDF completo/));
    await type("mario@cliente.it");
    await userEvent.click(send());
    expect(await screen.findByRole("alert")).toHaveTextContent("scegli un riepilogo");
    await userEvent.click(screen.getByRole("button", { name: "Passa al riepilogo" }));
    expect(screen.getByLabelText(/Riepilogo PDF/)).toBeChecked();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });
  it("il passaggio al riepilogo mantiene il formato (Excel resta Excel)", async () => {
    post.mockResolvedValue(fail(403, "no"));
    view();
    await userEvent.click(screen.getByLabelText(/Excel completo/));
    await type("mario@cliente.it");
    await userEvent.click(send());
    await userEvent.click(await screen.findByRole("button", { name: "Passa al riepilogo" }));
    expect(screen.getByLabelText(/Riepilogo Excel/)).toBeChecked();
  });
  it("altri errori (limite orario) si mostrano senza il pulsante del riepilogo", async () => {
    post.mockResolvedValue(fail(429, "Hai raggiunto il limite di 20 invii all'ora"));
    view();
    await type("mario@cliente.it");
    await userEvent.click(send());
    expect(await screen.findByRole("alert")).toHaveTextContent("limite di 20 invii");
    expect(screen.queryByRole("button", { name: "Passa al riepilogo" })).not.toBeInTheDocument();
    expect(send()).toBeEnabled(); // si può riprovare
  });
  it("un invio in coda lo dice, uno rifiutato mostra l'errore", async () => {
    post.mockResolvedValueOnce(ok("queued"));
    const first = view();
    await type("mario@cliente.it");
    await userEvent.click(send());
    expect(await screen.findByRole("status")).toHaveTextContent("è in coda e il portale riprova da solo");
    first.unmount();
    post.mockResolvedValueOnce(ok("failed", { error: "indirizzo rifiutato" }));
    view();
    await type("mario@cliente.it");
    await userEvent.click(send());
    expect(await screen.findByRole("alert")).toHaveTextContent("rifiutato: indirizzo rifiutato");
  });
  it("chiudere la finestra azzera i campi", async () => {
    post.mockResolvedValue(ok());
    view();
    await type("mario@cliente.it");
    await userEvent.click(send());
    await userEvent.click(await screen.findByRole("button", { name: "Chiudi" }));
    expect(onClose).toHaveBeenCalledTimes(1);
    await waitFor(() => expect(screen.getByLabelText("Indirizzo del destinatario")).toHaveValue(""));
  });
});
