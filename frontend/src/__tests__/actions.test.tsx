import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

const calls: { method: string; path: string; body?: unknown }[] = [];
const respond = vi.fn();
const navigate = vi.fn();
vi.mock("react-router-dom", async (orig) => ({ ...(await orig<typeof import("react-router-dom")>()), useNavigate: () => navigate }));
vi.mock("../api/client", async () => {
  const { ApiError } = await import("../lib/errors");
  const make = (method: string) => async (path: string, opts?: { body?: unknown }) => {
    calls.push({ method, path, body: opts?.body });
    return respond(method, path, opts);
  };
  return {
    api: { GET: vi.fn(async () => ({ data: [], response: new Response() })), POST: make("POST"), DELETE: make("DELETE"), PUT: make("PUT"), use: () => {} },
    API_BASE: "",
    unwrap: (r: { data?: unknown; error?: unknown; response: Response }) => {
      if (r.error !== undefined || r.data === undefined) throw new ApiError(r.response.status, r.error);
      return r.data;
    },
  };
});

import { ActionsBar } from "../components/ActionsBar";
import type { CeDetail } from "../api/types";

const none = { edit: false, submit: false, withdraw: false, approve: false, reject: false, new_version: false, discard_version: false, realign: false, delete: false };
const detail = (actions: Partial<typeof none>, status = "draft"): CeDetail =>
  ({
    ce: { id: "c1", code: "PS-X", owner: { id: "u", full_name: "Anna" }, versions_count: 1 },
    version: { number: 1, status, revision: 3 },
    header: { client: { id: "k1", name: "Alfa" }, project_name: "Progetto", start_date: "2026-01-01", end_date: "2026-03-31" },
    actions: { ...none, ...actions },
  }) as unknown as CeDetail;

const ok = (data: unknown = { ce: { id: "c1" } }) => ({ data, response: new Response() });
const view = (d: CeDetail) =>
  render(<QueryClientProvider client={new QueryClient()}><MemoryRouter><ActionsBar detail={d} /></MemoryRouter></QueryClientProvider>);

beforeEach(() => { calls.length = 0; respond.mockReset(); navigate.mockReset(); respond.mockResolvedValue(ok()); });

describe("ActionsBar: si vede solo ciò che il server consente", () => {
  it("bozza dell'autore: modifica e invio", () => {
    view(detail({ edit: true, submit: true }));
    expect(screen.getByRole("link", { name: "Modifica" })).toHaveAttribute("href", "/ce/c1/modifica");
    expect(screen.getByRole("button", { name: "Invia in approvazione" })).toBeInTheDocument();
    for (const n of ["Approva", "Rifiuta", "Ritira", "Nuova versione"]) expect(screen.queryByRole("button", { name: n })).not.toBeInTheDocument();
  });
  it("in approvazione per l'admin: approva e rifiuta", () => {
    view(detail({ approve: true, reject: true }, "submitted"));
    expect(screen.getByRole("button", { name: "Approva" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Rifiuta" })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Modifica" })).not.toBeInTheDocument();
  });
  it("approvato: nuova versione", () => {
    view(detail({ new_version: true }, "approved"));
    expect(screen.getByRole("button", { name: "Nuova versione" })).toBeInTheDocument();
  });
  it("senza permessi nessuna azione tranne il menu (duplica è sempre disponibile agli editor)", async () => {
    view(detail({}));
    expect(screen.queryByRole("link", { name: "Modifica" })).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /Altre azioni/ }));
    expect(screen.getAllByRole("menuitem").map((m) => m.textContent)).toEqual(["Duplica come nuovo CE"]);
  });
  it("il menu mostra scarta, riallinea ed elimina solo se consentiti", async () => {
    view(detail({ discard_version: true, realign: true, delete: true }));
    await userEvent.click(screen.getByRole("button", { name: /Altre azioni/ }));
    expect(screen.getAllByRole("menuitem").map((m) => m.textContent)).toEqual(["Duplica come nuovo CE", "Scarta la versione in lavorazione", "Riallinea tariffe e calendario", "Elimina il CE"]);
  });
});

describe("ActionsBar: chiamate all'API", () => {
  it("l'invio chiede conferma e poi chiama l'endpoint giusto", async () => {
    view(detail({ submit: true }));
    await userEvent.click(screen.getByRole("button", { name: "Invia in approvazione" }));
    expect(calls).toHaveLength(0); // prima serve la conferma
    expect(await screen.findByText(/Inviare «PS-X» \(versione 1\)/)).toBeInTheDocument();
    await userEvent.click(screen.getAllByRole("button", { name: "Invia in approvazione" }).at(-1)!);
    await waitFor(() => expect(calls.map((c) => `${c.method} ${c.path}`)).toEqual(["POST /api/v1/ce/{ce_id}/submit"]));
  });
  it("il rifiuto non parte senza motivo e lo invia ripulito", async () => {
    view(detail({ reject: true }, "submitted"));
    await userEvent.click(screen.getByRole("button", { name: "Rifiuta" }));
    const confirm = screen.getAllByRole("button", { name: "Rifiuta" }).at(-1)!;
    expect(confirm).toBeDisabled();
    await userEvent.type(screen.getByLabelText(/Motivo del rifiuto/), "  Mancano i test  ");
    await userEvent.click(confirm);
    await waitFor(() => expect(calls[0]).toMatchObject({ path: "/api/v1/ce/{ce_id}/reject", body: { reason: "Mancano i test" } }));
  });
  it("la nuova versione porta all'editor", async () => {
    view(detail({ new_version: true }, "approved"));
    await userEvent.click(screen.getByRole("button", { name: "Nuova versione" }));
    await userEvent.click(screen.getByRole("button", { name: "Crea la versione" }));
    await waitFor(() => expect(navigate).toHaveBeenCalledWith("/ce/c1/modifica"));
  });
  it("mostra tutti i problemi elencati dal server e non chiude la finestra", async () => {
    respond.mockResolvedValue({ error: { detail: { message: "Il CE non è inviabile", issues: ["Il CE non è inviabile", "Manca il cliente", "Nessuna riga"] } }, response: new Response(null, { status: 422 }) });
    view(detail({ submit: true }));
    await userEvent.click(screen.getByRole("button", { name: "Invia in approvazione" }));
    await userEvent.click(screen.getAllByRole("button", { name: "Invia in approvazione" }).at(-1)!);
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Il CE non è inviabile");
    expect(alert).toHaveTextContent("Manca il cliente");
    expect(alert).toHaveTextContent("Nessuna riga");
    expect(screen.getByRole("button", { name: "Annulla" })).toBeInTheDocument(); // la finestra resta aperta
    expect(navigate).not.toHaveBeenCalled();
  });
  it("l'eliminazione porta all'elenco", async () => {
    respond.mockResolvedValue({ error: undefined, response: new Response(null, { status: 204 }) });
    view(detail({ delete: true }));
    await userEvent.click(screen.getByRole("button", { name: /Altre azioni/ }));
    await userEvent.click(screen.getByRole("menuitem", { name: "Elimina il CE" }));
    await userEvent.click(screen.getAllByRole("button", { name: "Elimina" }).at(-1)!);
    await waitFor(() => expect(navigate).toHaveBeenCalledWith("/ce"));
    expect(calls[0]).toMatchObject({ method: "DELETE", path: "/api/v1/ce/{ce_id}" });
  });
});
