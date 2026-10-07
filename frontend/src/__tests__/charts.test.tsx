import { render, screen, within } from "@testing-library/react";

import { BarChart, HBars, SERIES_APPROVED, SERIES_PIPELINE } from "../components/charts/BarChart";
import { HEAT_CLASS, compact, heatLevel, niceMax } from "../lib/scale";
import { money } from "../lib/format";

describe("scale", () => {
  it.each([[0, 1], [-5, 1], [0.7, 1], [1, 1], [1.2, 2], [2.4, 2.5], [3, 5], [5.1, 10], [83_000, 100_000], [100_000, 100_000], [1_240_000, 2_000_000], [47_162.5, 50_000]])("niceMax(%s) = %s", (input, expected) => expect(niceMax(input)).toBe(expected));
  it("compact: numeri brevi per gli assi, con la virgola", () => {
    expect(compact(0)).toBe("0");
    expect(compact(850)).toBe("850");
    expect(compact(1500)).toBe("1,5 k");
    expect(compact(120_000)).toBe("120 k");
    expect(compact(1_200_000)).toBe("1,2 M");
    expect(compact(2_000_000)).toBe("2 M");
  });
  it("livelli di impegno: il 100% esatto non è sovraccarico", () => {
    expect(heatLevel(null, false)).toBe("empty");
    expect(heatLevel(0, false)).toBe("empty");
    expect(heatLevel(0.5, false)).toBe("low");
    expect(heatLevel(0.51, false)).toBe("high");
    expect(heatLevel(1, false)).toBe("high");
    expect(heatLevel(1.2, true)).toBe("over");
    expect(HEAT_CLASS.over).toContain("bg-red-600");
  });
});

const data = [
  { label: "gen 2026", values: { approved: 18_000, pipeline: 0 } },
  { label: "feb 2026", values: { approved: 24_000, pipeline: 8_000 } },
];

describe("BarChart", () => {
  it("disegna una barra per ogni serie con valore e nessuna per gli zeri", () => {
    const { container } = render(<BarChart title="Ricavi per mese" data={data} series={[SERIES_APPROVED, SERIES_PIPELINE]} format={money} />);
    expect(container.querySelectorAll("svg rect[stroke='#0a0a0a'][height]").length).toBeGreaterThanOrEqual(3); // 3 segmenti con valore
    const titles = Array.from(container.querySelectorAll("svg rect title")).map((t) => t.textContent);
    expect(titles).toEqual(["gen 2026 · Approvati: 18.000,00 €", "feb 2026 · Approvati: 24.000,00 €", "feb 2026 · Pipeline: 8.000,00 €"]);
  });
  it("le barre sono proporzionali ai valori", () => {
    const { container } = render(<BarChart title="T" data={[{ label: "a", values: { approved: 100 } }, { label: "b", values: { approved: 50 } }]} series={[SERIES_APPROVED]} format={String} />);
    const heights = Array.from(container.querySelectorAll("svg rect[height]")).map((r) => Number(r.getAttribute("height")));
    expect(heights[0]).toBeCloseTo(heights[1] * 2, 1);
  });
  it("le barre impilate si appoggiano l'una sull'altra, senza buchi né sovrapposizioni", () => {
    const { container } = render(<BarChart title="T" data={[{ label: "a", values: { approved: 60, pipeline: 40 } }]} series={[SERIES_APPROVED, SERIES_PIPELINE]} format={String} />);
    const [approved, pipeline] = Array.from(container.querySelectorAll("svg g > rect")).map((r) => ({ y: Number(r.getAttribute("y")), h: Number(r.getAttribute("height")) }));
    expect(pipeline.y + pipeline.h).toBeCloseTo(approved.y, 3); // la base della pipeline è la cima degli approvati
    expect(approved.h / pipeline.h).toBeCloseTo(60 / 40, 2);
  });
  it("ha una tabella con gli stessi dati per i lettori di schermo, e la parte grafica è nascosta", () => {
    const { container } = render(<BarChart title="Ricavi per mese" data={data} series={[SERIES_APPROVED, SERIES_PIPELINE]} format={money} />);
    const table = screen.getByRole("table", { name: "Ricavi per mese" });
    expect(within(table).getByRole("rowheader", { name: "feb 2026" })).toBeInTheDocument();
    expect(within(table).getAllByRole("cell").map((c) => c.textContent)).toEqual(["18.000,00 €", "0,00 €", "24.000,00 €", "8.000,00 €"]);
    expect(container.querySelector("svg")!.closest("[aria-hidden]")).not.toBeNull();
  });
  it("la legenda nomina le serie (non conta solo il colore)", () => {
    render(<BarChart title="T" data={data} series={[SERIES_APPROVED, SERIES_PIPELINE]} format={String} />);
    const legend = screen.getByRole("list", { name: "Legenda" });
    expect(within(legend).getByText("Approvati")).toBeInTheDocument();
    expect(within(legend).getByText("Pipeline")).toBeInTheDocument();
  });
  it("senza dati non si rompe", () => {
    const { container } = render(<BarChart title="Vuoto" data={[]} series={[SERIES_APPROVED]} format={String} />);
    expect(container.querySelector("svg")).not.toBeNull();
  });
});

describe("HBars", () => {
  const rows = ["Alfa", "Beta", "Gamma", "Delta"].map((label, i) => ({ label, values: { approved: (i + 1) * 100, pipeline: 0 } }));
  it("ordina dal più grande e mostra il valore scritto", () => {
    render(<HBars title="Ricavi per cliente" rows={rows} series={[SERIES_APPROVED]} format={money} />);
    const table = screen.getByRole("table", { name: "Ricavi per cliente" });
    expect(within(table).getAllByRole("rowheader").map((h) => h.textContent)).toEqual(["Delta", "Gamma", "Beta", "Alfa"]);
    expect(screen.getAllByText("400,00 €")).toHaveLength(2); // nel grafico e nella tabella per i lettori di schermo
  });
  it("raggruppa il resto in «Altri» oltre il limite", () => {
    render(<HBars title="T" rows={rows} series={[SERIES_APPROVED]} format={String} limit={2} />);
    const table = screen.getByRole("table", { name: "T" });
    expect(within(table).getAllByRole("rowheader").map((h) => h.textContent)).toEqual(["Delta", "Gamma", "Altri (2)"]);
    expect(within(table).getAllByRole("cell").map((c) => c.textContent)).toEqual(["400", "300", "300"]); // Beta 200 + Alfa 100
  });
  it("senza dati lo dice", () => {
    render(<HBars title="T" rows={[]} series={[SERIES_APPROVED]} format={String} />);
    expect(screen.getByText("Nessun dato nel periodo.")).toBeInTheDocument();
  });
});
