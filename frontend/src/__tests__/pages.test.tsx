import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";

const get = vi.fn();
const post = vi.fn();
vi.mock("../api/client", async () => {
  const { ApiError } = await import("../lib/errors");
  return {
    api: { GET: (...a: unknown[]) => get(...a), POST: (...a: unknown[]) => post(...a), use: () => {} },
    API_BASE: "",
    unwrap: (r: { data?: unknown; error?: unknown; response: Response }) => {
      if (r.error !== undefined || r.data === undefined) throw new ApiError(r.response.status, r.error);
      return r.data;
    },
  };
});

let role = "presale";
const signIn = vi.fn();
vi.mock("../auth/AuthContext", () => ({
  useAuth: () => ({
    user: { id: "u1", full_name: "Anna Presale", role },
    isEditor: role !== "viewer", isAdmin: role === "admin", signIn, signOut: vi.fn(),
    state: { status: "authed" },
  }),
}));

import { CeListPage } from "../pages/CeListPage";

const ok = (data: unknown) => ({ data, response: new Response() });
const wrap = (ui: React.ReactNode, route = "/ce") => {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[route]}><Routes><Route path="/ce" element={ui} /><Route path="*" element={ui} /></Routes></MemoryRouter>
    </QueryClientProvider>,
  );
};

const editorItem = {
  ce_id: "c1", code: "PS-TEST-1", client: { id: "k1", name: "Alfa" }, project_name: "Progetto uno", start_date: "2026-01-20", end_date: "2026-04-20",
  planning_mode: "hours", version_number: 2, status: "submitted", owner: { id: "u1", full_name: "Anna Presale" }, updated_at: "2026-10-06T12:30:00Z",
  deleted: false, price: "47162.50", margin_pct: "0.5717", days_total: "58.5",
};

beforeEach(() => {
  get.mockReset(); post.mockReset(); signIn.mockReset(); role = "presale";
  get.mockImplementation(async (path: string) => {
    if (path === "/api/v1/clients/lookup") return ok([{ id: "k1", name: "Alfa" }]);
    if (path === "/api/v1/ce") return ok({ items: [editorItem], total: 1, limit: 20, offset: 0 });
    if (path === "/api/v1/ce/summaries") return ok({ items: [{ ce_id: "c1", code: "PS-TEST-1", client_name: "Alfa", project_name: "Progetto uno", start_date: "2026-01-20", end_date: "2026-04-20", version_number: 1, approved_at: "2026-02-01T10:00:00Z", price: "47162.50" }], total: 1, limit: 20, offset: 0 });
    throw new Error("chiamata inattesa " + path);
  });
});

describe("CeListPage", () => {
  it("editor: mostra stato, autore, prezzo e margine nei formati italiani", async () => {
    wrap(<CeListPage />);
    expect(await screen.findAllByText("PS-TEST-1")).not.toHaveLength(0);
    expect(screen.getAllByText("In approvazione").length).toBeGreaterThan(0);
    expect(screen.getAllByText("47.162,50 €").length).toBeGreaterThan(0);
    expect(screen.getAllByText("57,17%").length).toBeGreaterThan(0);
    expect(screen.getByText("conto economico")).toBeInTheDocument();
    expect(get).toHaveBeenCalledWith("/api/v1/ce", { params: { query: { limit: 20, offset: 0 } } });
  });
  it("viewer: usa l'elenco ridotto e non mostra margine, autore né stato", async () => {
    role = "viewer";
    wrap(<CeListPage />);
    expect(await screen.findAllByText("PS-TEST-1")).not.toHaveLength(0);
    expect(get).toHaveBeenCalledWith("/api/v1/ce/summaries", expect.anything());
    expect(get).not.toHaveBeenCalledWith("/api/v1/ce", expect.anything());
    expect(screen.queryByText("Margine")).not.toBeInTheDocument();
    expect(screen.queryByText("Autore")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Stato")).not.toBeInTheDocument();
    expect(screen.queryByText("57,17%")).not.toBeInTheDocument();
  });
  it("un filtro interroga di nuovo l'API con il parametro giusto", async () => {
    wrap(<CeListPage />);
    await screen.findAllByText("PS-TEST-1");
    await userEvent.selectOptions(screen.getByLabelText("Stato"), "approved");
    await waitFor(() => expect(get).toHaveBeenCalledWith("/api/v1/ce", { params: { query: { status: "approved", limit: 20, offset: 0 } } }));
  });
  it("mostra un messaggio chiaro se non ci sono risultati", async () => {
    get.mockImplementation(async (path: string) => (path === "/api/v1/clients/lookup" ? ok([]) : ok({ items: [], total: 0, limit: 20, offset: 0 })));
    wrap(<CeListPage />, "/ce?code=zzz");
    expect(await screen.findByRole("heading", { name: "Nessun risultato" })).toBeInTheDocument();
  });
  it("mostra l'errore dell'API e permette di riprovare", async () => {
    get.mockImplementation(async (path: string) => (path === "/api/v1/clients/lookup" ? ok([]) : { error: { detail: "Database non raggiungibile" }, response: new Response(null, { status: 500 }) }));
    wrap(<CeListPage />);
    expect(await screen.findByRole("alert")).toHaveTextContent("Database non raggiungibile");
    expect(screen.getByRole("button", { name: "Riprova" })).toBeInTheDocument();
  });
});
