import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { StatusBadge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Menu } from "../components/ui/Menu";
import { Pagination } from "../components/ui/Pagination";
import { ScrollArea } from "../components/ui/ScrollArea";

describe("StatusBadge", () => {
  it.each([["draft", "Bozza"], ["submitted", "In approvazione"], ["approved", "Approvato"], ["rejected", "Rifiutato"]])("%s -> %s", (status, label) => {
    render(<StatusBadge status={status} />);
    expect(screen.getByText(label)).toBeInTheDocument();
  });
  it("uno stato sconosciuto non rompe la pagina", () => {
    render(<StatusBadge status="boh" />);
    expect(screen.getByText("Bozza")).toBeInTheDocument();
  });
});

describe("Button", () => {
  it("in caricamento è disabilitato e lo comunica", () => {
    render(<Button loading>Salva</Button>);
    expect(screen.getByRole("button", { name: "Salva" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Salva" })).toHaveAttribute("aria-busy", "true");
  });
});

describe("Pagination", () => {
  it("non compare se basta una pagina", () => {
    const { container } = render(<Pagination total={10} limit={20} offset={0} onChange={() => {}} />);
    expect(container).toBeEmptyDOMElement();
  });
  it("naviga avanti e indietro e disabilita i limiti", async () => {
    const onChange = vi.fn();
    const { rerender } = render(<Pagination total={45} limit={20} offset={0} onChange={onChange} />);
    expect(screen.getByText("Pagina 1 di 3")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Precedente/ })).toBeDisabled();
    await userEvent.click(screen.getByRole("button", { name: /Successiva/ }));
    expect(onChange).toHaveBeenCalledWith(20);
    rerender(<Pagination total={45} limit={20} offset={40} onChange={onChange} />);
    expect(screen.getByRole("button", { name: /Successiva/ })).toBeDisabled();
    await userEvent.click(screen.getByRole("button", { name: /Precedente/ }));
    expect(onChange).toHaveBeenCalledWith(20);
  });
});

describe("Menu", () => {
  it("si apre, esegue la voce scelta e si chiude", async () => {
    const onSelect = vi.fn();
    render(<Menu label="Esporta" items={[{ label: "Excel", onSelect }, "separator", { label: "CSV", onSelect: () => {} }]} />);
    expect(screen.queryByRole("menu")).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /Esporta/ }));
    expect(screen.getByRole("menu")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("menuitem", { name: "Excel" }));
    expect(onSelect).toHaveBeenCalledTimes(1);
    expect(screen.queryByRole("menu")).not.toBeInTheDocument();
  });
  it("si chiude con Esc e cliccando fuori", async () => {
    render(<div><Menu label="Esporta" items={[{ label: "Excel", onSelect: () => {} }]} /><p>fuori</p></div>);
    const trigger = screen.getByRole("button", { name: /Esporta/ });
    await userEvent.click(trigger);
    await userEvent.keyboard("{Escape}");
    expect(screen.queryByRole("menu")).not.toBeInTheDocument();
    await userEvent.click(trigger);
    await userEvent.click(screen.getByText("fuori"));
    expect(screen.queryByRole("menu")).not.toBeInTheDocument();
  });
});

describe("ScrollArea", () => {
  it("è una regione con nome, raggiungibile con la tastiera", () => {
    render(<ScrollArea label="Righe della fase X"><table /></ScrollArea>);
    const region = screen.getByRole("region", { name: "Righe della fase X" });
    expect(region).toHaveAttribute("tabindex", "0");
  });
});
