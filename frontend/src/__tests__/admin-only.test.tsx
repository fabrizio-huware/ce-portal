import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

let role = "admin";
vi.mock("../auth/AuthContext", () => ({ useAuth: () => ({ isAdmin: role === "admin", isEditor: role !== "viewer", user: { role } }) }));

import { AdminHeader, AdminOnly } from "../components/admin/AdminHeader";
import { EditorsOnly } from "../pages/dashboard/DashboardTabs";

const inRouter = (ui: React.ReactNode) => render(<MemoryRouter>{ui}</MemoryRouter>);

describe("AdminOnly", () => {
  it.each([["presale"], ["viewer"]])("a un %s mostra un avviso e non il contenuto", (r) => {
    role = r;
    inRouter(<AdminOnly><p>Segreto</p></AdminOnly>);
    expect(screen.queryByText("Segreto")).not.toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveTextContent("riservata agli amministratori");
  });
  it("all'admin mostra il contenuto", () => {
    role = "admin";
    inRouter(<AdminOnly><p>Segreto</p></AdminOnly>);
    expect(screen.getByText("Segreto")).toBeInTheDocument();
  });
});

describe("EditorsOnly (dashboard)", () => {
  it("il viewer non vede le dashboard, il presale sì", () => {
    role = "viewer";
    const { unmount } = inRouter(<EditorsOnly><p>Margini</p></EditorsOnly>);
    expect(screen.queryByText("Margini")).not.toBeInTheDocument();
    unmount();
    role = "presale";
    inRouter(<EditorsOnly><p>Margini</p></EditorsOnly>);
    expect(screen.getByText("Margini")).toBeInTheDocument();
  });
});

describe("AdminHeader", () => {
  it("ha tutte le schede e il sottotitolo", () => {
    role = "admin";
    inRouter(<AdminHeader subtitle="Chi può accedere" />);
    const nav = screen.getByRole("navigation", { name: "Amministrazione" });
    expect(Array.from(nav.querySelectorAll("a")).map((a) => a.textContent)).toEqual(["Utenti", "Clienti", "Collaboratori", "Listino", "Calendario", "Email", "CE eliminati"]);
    expect(screen.getByText("Chi può accedere")).toBeInTheDocument();
  });
});
