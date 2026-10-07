import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const upload = vi.fn();
vi.mock("../api/upload", () => ({ uploadCsv: (...a: unknown[]) => upload(...a) }));

import { ImportDialog } from "../components/admin/ImportDialog";

const result = (over: Record<string, unknown> = {}) => ({ dry_run: true, applied: false, total_rows: 3, created: 2, updated: 1, unchanged: 0, extra: {}, errors: [], ...over });
const file = new File(["Nome;Cognome\nA;B"], "dati.csv", { type: "text/csv" });
const onDone = vi.fn();
const view = () => render(<ImportDialog open onClose={() => {}} title="Importa prova" path="/api/v1/x/import" columns={<>a; b</>} example="/esempi/x.csv" onDone={onDone} />);
const choose = async () => userEvent.upload(screen.getByLabelText("File CSV"), file);

beforeEach(() => { upload.mockReset(); onDone.mockReset(); });

describe("ImportDialog", () => {
  it("prima si controlla il file: nulla viene scritto", async () => {
    upload.mockResolvedValue(result());
    view();
    expect(screen.getByRole("button", { name: "Controlla il file" })).toBeDisabled(); // senza file
    await choose();
    await userEvent.click(screen.getByRole("button", { name: "Controlla il file" }));
    expect(upload).toHaveBeenCalledWith("/api/v1/x/import", file, true); // dry_run
    expect(await screen.findByRole("status")).toHaveTextContent("Il file è corretto: 3 righe");
    expect(screen.getByRole("status")).toHaveTextContent("2 nuovi · 1 da aggiornare");
    expect(onDone).not.toHaveBeenCalled();
  });
  it("poi si conferma: importa davvero e avvisa", async () => {
    upload.mockResolvedValueOnce(result()).mockResolvedValueOnce(result({ dry_run: false, applied: true, extra: { profili_creati: 1 } }));
    view();
    await choose();
    await userEvent.click(screen.getByRole("button", { name: "Controlla il file" }));
    await userEvent.click(await screen.findByRole("button", { name: "Importa" }));
    expect(upload).toHaveBeenLastCalledWith("/api/v1/x/import", file, false);
    expect(await screen.findByText(/Importazione completata/)).toBeInTheDocument();
    expect(screen.getByText(/profili creati: 1/)).toBeInTheDocument();
    expect(onDone).toHaveBeenCalledTimes(1);
  });
  it("con errori elenca le righe e non permette di importare", async () => {
    upload.mockResolvedValue(result({ errors: [{ line: 3, message: "Profilo sconosciuto" }, { line: null, message: "Intestazione mancante" }] }));
    view();
    await choose();
    await userEvent.click(screen.getByRole("button", { name: "Controlla il file" }));
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("2 errori: non è stato importato nulla");
    expect(alert).toHaveTextContent("Riga 3: Profilo sconosciuto");
    expect(alert).toHaveTextContent("Intestazione mancante");
    expect(screen.queryByRole("button", { name: "Importa" })).not.toBeInTheDocument();
    expect(onDone).not.toHaveBeenCalled();
  });
  it("se non c'è nulla da cambiare lo dice e non si importa", async () => {
    upload.mockResolvedValue(result({ created: 0, updated: 0, unchanged: 3 }));
    view();
    await choose();
    await userEvent.click(screen.getByRole("button", { name: "Controlla il file" }));
    expect(await screen.findByText("Non c'è nulla da cambiare.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Importa" })).toBeDisabled();
  });
  it("un file vuoto (0 righe) non si può importare", async () => {
    upload.mockResolvedValue(result({ total_rows: 0, created: 0, updated: 0 }));
    view();
    await choose();
    await userEvent.click(screen.getByRole("button", { name: "Controlla il file" }));
    await waitFor(() => expect(upload).toHaveBeenCalled());
    expect(screen.queryByRole("button", { name: "Importa" })).not.toBeInTheDocument();
  });
  it("cambiando file l'anteprima precedente sparisce", async () => {
    upload.mockResolvedValue(result({ errors: [{ line: 2, message: "Errore" }] }));
    view();
    await choose();
    await userEvent.click(screen.getByRole("button", { name: "Controlla il file" }));
    await screen.findByRole("alert");
    await userEvent.upload(screen.getByLabelText("File CSV"), new File(["x"], "altro.csv", { type: "text/csv" }));
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });
  it("un errore del server (file non valido) è mostrato", async () => {
    upload.mockRejectedValue(new Error("Il file non è un CSV valido"));
    view();
    await choose();
    await userEvent.click(screen.getByRole("button", { name: "Controlla il file" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Il file non è un CSV valido");
  });
  it("offre il file di esempio da scaricare", () => {
    view();
    expect(screen.getByRole("link", { name: "Scarica un file di esempio" })).toHaveAttribute("href", "/esempi/x.csv");
  });
});
