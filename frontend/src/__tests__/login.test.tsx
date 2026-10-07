import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

const post = vi.fn();
const get = vi.fn();
const signIn = vi.fn();
vi.mock("../api/client", async () => {
  const { ApiError } = await import("../lib/errors");
  return {
    api: { POST: (...a: unknown[]) => post(...a), GET: (...a: unknown[]) => get(...a), use: () => {} },
    API_BASE: "",
    unwrap: (r: { data?: unknown; error?: unknown; response: Response }) => {
      if (r.error !== undefined || r.data === undefined) throw new ApiError(r.response.status, r.error);
      return r.data;
    },
  };
});
vi.mock("../auth/AuthContext", () => ({ useAuth: () => ({ state: { status: "anon", expired: false }, signIn }) }));

import { LoginPage } from "../pages/LoginPage";

const ok = (data: unknown) => ({ data, response: new Response() });
const config = (c: { google_client_id: string | null; dev_login: boolean }) => get.mockResolvedValue(ok(c));
const renderLogin = () =>
  render(<QueryClientProvider client={new QueryClient()}><MemoryRouter><LoginPage /></MemoryRouter></QueryClientProvider>);

beforeEach(() => { post.mockReset(); get.mockReset(); signIn.mockReset(); });

describe("LoginPage: cosa mostrare lo decide il server", () => {
  it("in locale: accesso simulato, invia l'email e apre la sessione con il token ricevuto", async () => {
    config({ google_client_id: null, dev_login: true });
    post.mockResolvedValue(ok({ access_token: "tok", user: { id: "u1", role: "admin" } }));
    renderLogin();
    await userEvent.type(await screen.findByLabelText("Email di un utente registrato"), "admin@huware.com");
    await userEvent.click(screen.getByRole("button", { name: "Entra senza Google" }));
    await waitFor(() => expect(signIn).toHaveBeenCalledWith("tok", { id: "u1", role: "admin" }));
    expect(get).toHaveBeenCalledWith("/api/v1/config");
    expect(post).toHaveBeenCalledWith("/api/v1/auth/dev-login", { body: { email: "admin@huware.com" } });
  });
  it("mostra il motivo se l'accesso è negato e non apre la sessione", async () => {
    config({ google_client_id: null, dev_login: true });
    post.mockResolvedValue({ error: { detail: "Utente non abilitato" }, response: new Response(null, { status: 403 }) });
    renderLogin();
    await userEvent.type(await screen.findByLabelText("Email di un utente registrato"), "x@huware.com");
    await userEvent.click(screen.getByRole("button", { name: "Entra senza Google" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Utente non abilitato");
    expect(signIn).not.toHaveBeenCalled();
  });
  it("in produzione senza Client ID: nessun accesso di sviluppo e un avviso chiaro", async () => {
    config({ google_client_id: null, dev_login: false });
    renderLogin();
    expect(await screen.findByRole("alert")).toHaveTextContent("non è ancora configurato");
    expect(screen.queryByLabelText("Email di un utente registrato")).not.toBeInTheDocument();
  });
  it("in produzione con il Client ID: il pulsante di Google e nessun accesso di sviluppo", async () => {
    config({ google_client_id: "abc.apps.googleusercontent.com", dev_login: false });
    renderLogin();
    expect(await screen.findByLabelText("Accedi con Google")).toBeInTheDocument();
    expect(screen.queryByLabelText("Email di un utente registrato")).not.toBeInTheDocument();
  });
  it("un server che non risponde non lascia la pagina vuota", async () => {
    get.mockResolvedValue({ error: { detail: "giù" }, response: new Response(null, { status: 503 }) });
    renderLogin();
    expect(await screen.findByRole("alert", undefined, { timeout: 5000 })).toHaveTextContent("Impossibile contattare il server");
    expect(screen.getByRole("button", { name: "Riprova" })).toBeInTheDocument();
  });
});
