import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";

const clients = vi.fn();
vi.mock("../api/lookups", () => ({ useClients: () => clients() }));
vi.mock("../api/client", () => ({ api: { POST: vi.fn() }, API_BASE: "", unwrap: (r: { data: unknown }) => r.data }));

import { ClientSelect, selectable } from "../components/ClientSelect";

const list = [
  { id: "a", name: "Alfa Retail", is_active: true },
  { id: "b", name: "Beta Banca", is_active: false },
  { id: "c", name: "Gamma Energia", is_active: true },
];

describe("selectable", () => {
  it("offre i clienti attivi e non quelli disattivati", () => {
    expect(selectable(list, "").map((c) => c.id)).toEqual(["a", "c"]);
  });
  it("tiene il cliente già assegnato anche se è stato disattivato", () => {
    expect(selectable(list, "b").map((c) => c.id)).toEqual(["a", "b", "c"]);
  });
  it("un cliente già assegnato e attivo non compare due volte", () => {
    expect(selectable(list, "a").map((c) => c.id)).toEqual(["a", "c"]);
  });
  it("un identificativo sconosciuto non aggiunge nulla e non rompe", () => {
    expect(selectable(list, "zzz").map((c) => c.id)).toEqual(["a", "c"]);
    expect(selectable([], "a")).toEqual([]);
  });
});

describe("ClientSelect", () => {
  const view = (value: string) =>
    render(<QueryClientProvider client={new QueryClient()}><ClientSelect id="cs" value={value} onChange={() => {}} /></QueryClientProvider>);
  beforeEach(() => clients.mockReturnValue({ data: list }));

  it("nel menu ci sono solo i clienti attivi", () => {
    view("");
    expect(screen.getAllByRole("option").map((o) => o.textContent)).toEqual(["Scegli il cliente…", "Alfa Retail", "Gamma Energia"]);
  });
  it("il cliente disattivato già assegnato resta selezionato e dichiara di essere disattivato", () => {
    view("b");
    expect(screen.getByRole("combobox")).toHaveValue("b");
    expect(screen.getByRole("option", { name: "Beta Banca (disattivato)" })).toBeInTheDocument();
    expect(screen.queryByRole("option", { name: "Beta Banca" })).not.toBeInTheDocument();
  });
  it("durante il caricamento non si rompe", () => {
    clients.mockReturnValue({ data: undefined });
    view("");
    expect(screen.getAllByRole("option")).toHaveLength(1);
  });
});
