import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

const post = vi.fn();
const signIn = vi.fn();
vi.mock("../api/client", async () => {
  const { ApiError } = await import("../lib/errors");
  return {
    api: { POST: (...a: unknown[]) => post(...a), GET: vi.fn(), use: () => {} },
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
const renderLogin = () =>
  render(<QueryClientProvider client={new QueryClient()}><MemoryRouter><LoginPage /></MemoryRouter></QueryClientProvider>);

beforeEach(() => { post.mockReset(); signIn.mockReset(); });
afterEach(() => vi.unstubAllEnvs());

describe("LoginPage", () => {
  it("con l'accesso di sviluppo: invia l'email e apre la sessione con il token ricevuto", async () => {
    vi.stubEnv("VITE_ENABLE_DEV_LOGIN", "true");
    post.mockResolvedValue(ok({ access_token: "tok", user: { id: "u1", role: "admin" } }));
    renderLogin();
    await userEvent.type(screen.getByLabelText("Email di un utente registrato"), "admin@huware.com");
    await userEvent.click(screen.getByRole("button", { name: "Entra senza Google" }));
    await waitFor(() => expect(signIn).toHaveBeenCalledWith("tok", { id: "u1", role: "admin" }));
    expect(post).toHaveBeenCalledWith("/api/v1/auth/dev-login", { body: { email: "admin@huware.com" } });
  });
  it("mostra il motivo se l'accesso è negato e non apre la sessione", async () => {
    vi.stubEnv("VITE_ENABLE_DEV_LOGIN", "true");
    post.mockResolvedValue({ error: { detail: "Utente non abilitato" }, response: new Response(null, { status: 403 }) });
    renderLogin();
    await userEvent.type(screen.getByLabelText("Email di un utente registrato"), "x@huware.com");
    await userEvent.click(screen.getByRole("button", { name: "Entra senza Google" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Utente non abilitato");
    expect(signIn).not.toHaveBeenCalled();
  });
  it("in produzione l'accesso di sviluppo non esiste", () => {
    vi.stubEnv("VITE_ENABLE_DEV_LOGIN", "false");
    vi.stubEnv("VITE_GOOGLE_CLIENT_ID", "");
    renderLogin();
    expect(screen.queryByLabelText("Email di un utente registrato")).not.toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveTextContent("non è ancora configurato");
  });
  it("con il Client ID di Google non mostra l'accesso di sviluppo e prepara il pulsante", () => {
    vi.stubEnv("VITE_ENABLE_DEV_LOGIN", "false");
    vi.stubEnv("VITE_GOOGLE_CLIENT_ID", "abc.apps.googleusercontent.com");
    renderLogin();
    expect(screen.getByLabelText("Accedi con Google")).toBeInTheDocument();
    expect(screen.queryByLabelText("Email di un utente registrato")).not.toBeInTheDocument();
  });
});
