import { CELL_MODES, cellModeParam, daysText, formatLoadCell, hoursText, parseCellMode, roundHalfUp } from "../lib/loadCell";

// le ore le fornisce il server (giorni × 8): negli esempi sono coerenti, a meno che il test dica altro
const cell = (fte: string | null, days: string, overloaded = false, hours = (Number(days) * 8).toFixed(4)) => ({ fte, days, hours, overloaded });

describe("formatLoadCell", () => {
  it("predefinito «entrambi»: percentuale in evidenza e giorni sotto, con un decimale", () => {
    expect(formatLoadCell("both", cell("0.5400", "10.8000"))).toEqual({ primary: "54%", secondary: "10,8 gg", empty: false });
    expect(formatLoadCell("both", cell("1.0000", "22.0000"))).toEqual({ primary: "100%", secondary: "22,0 gg", empty: false });
  });
  it("solo percentuale (com'era prima) e solo giorni", () => {
    expect(formatLoadCell("pct", cell("0.95", "19.95"))).toEqual({ primary: "95%", secondary: null, empty: false });
    expect(formatLoadCell("days", cell("0.95", "19.95"))).toEqual({ primary: "20,0", secondary: null, empty: false });
  });
  it("modalità ore: solo le ore del server, con un decimale e senza unità", () => {
    expect(formatLoadCell("hours", cell("0.5400", "10.8000"))).toEqual({ primary: "86,4", secondary: null, empty: false });
    expect(formatLoadCell("hours", cell("0.0200", "0.5000"))).toEqual({ primary: "4,0", secondary: null, empty: false }); // 0,5 gg = 4 ore
    expect(formatLoadCell("hours", cell("1.0000", "22.0000"))).toEqual({ primary: "176,0", secondary: null, empty: false });
    expect(formatLoadCell("hours", cell("1.8750", "37.5000", true))).toEqual({ primary: "⚠ 300,0", secondary: null, empty: false });
  });
  it("le ore non si ricavano dai giorni nel browser: si mostra quello che dice il server", () => {
    expect(formatLoadCell("hours", cell("0.5", "10", false, "81.2500")).primary).toBe("81,3"); // arrotondato da 5 in su, non 10 × 8
  });
  it("le ore si arrotondano da 5 in su come i giorni, e un impegno minuscolo non diventa «0,0»", () => {
    expect(hoursText("19.95")).toBe("20,0");
    expect(hoursText("1234.55")).toBe("1.234,6");
    expect(hoursText("0.04")).toBe("<0,1");
    expect(hoursText("0.05")).toBe("0,1");
    expect(formatLoadCell("hours", cell("0.001", "0.003", false, "0.0240")).primary).toBe("<0,1");
  });
  it("il sovraccarico ha il ⚠ in ogni modalità: il colore non è l'unica informazione", () => {
    for (const mode of ["both", "pct", "days", "hours"] as const) {
      expect(formatLoadCell(mode, cell("1.12", "24.64", true)).primary.startsWith("⚠ ")).toBe(true);
    }
    expect(formatLoadCell("both", cell("1.12", "24.64", true))).toEqual({ primary: "⚠ 112%", secondary: "24,6 gg", empty: false });
  });
  it("nessun impegno: trattino, in ogni modalità", () => {
    for (const mode of ["both", "pct", "days", "hours"] as const) {
      expect(formatLoadCell(mode, cell(null, "0"))).toEqual({ primary: "—", secondary: null, empty: true });
      expect(formatLoadCell(mode, cell("0", "0.0000"))).toEqual({ primary: "—", secondary: null, empty: true });
      expect(formatLoadCell(mode, { fte: undefined, days: "5", hours: "40", overloaded: false }).empty).toBe(true);
    }
  });
  it("arrotonda alla maniera italiana e non perde mezzi giorni", () => {
    expect(formatLoadCell("days", cell("0.2", "4.45")).primary).toBe("4,5");
    expect(formatLoadCell("days", cell("0.2", "4.4"))).toMatchObject({ primary: "4,4" });
    expect(formatLoadCell("days", cell("0.9", "123.45")).primary).toBe("123,5");
    expect(formatLoadCell("days", cell("0.9", "1234.5")).primary).toBe("1.234,5");
  });
  it("un impegno minuscolo ma reale non appare come «0,0»", () => {
    expect(daysText("0.03")).toBe("<0,1");
    expect(daysText("0.05")).toBe("0,1");
    expect(formatLoadCell("both", cell("0.001", "0.03")).secondary).toBe("<0,1 gg");
  });
});

describe("modalità nell'indirizzo", () => {
  it("«entrambi» è il predefinito e non si scrive; le altre sì", () => {
    expect(cellModeParam("both")).toBeNull();
    expect(cellModeParam("pct")).toBe("pct");
    expect(cellModeParam("days")).toBe("giorni");
    expect(cellModeParam("hours")).toBe("ore");
  });
  it("si legge qualunque valore, anche sbagliato, senza rompersi", () => {
    expect(parseCellMode(null)).toBe("both");
    expect(parseCellMode(undefined)).toBe("both");
    expect(parseCellMode("")).toBe("both");
    expect(parseCellMode("pct")).toBe("pct");
    expect(parseCellMode("giorni")).toBe("days");
    expect(parseCellMode("ore")).toBe("hours");
    for (const bad of ["days", "hours", "Giorni", "Ore", "tutto", "1", "<script>"]) expect(parseCellMode(bad)).toBe("both");
  });
  it("scrivere e rileggere dà lo stesso risultato", () => {
    for (const { value } of CELL_MODES) expect(parseCellMode(cellModeParam(value))).toBe(value);
  });
  it("le tre scelte ci sono, con le etichette che l'utente vede", () => {
    expect(CELL_MODES.map((m) => m.label)).toEqual(["Percentuale", "Giorni", "Ore", "Entrambi"]);
  });
});

describe("roundHalfUp: «da 5 in su» come il server ed Excel, senza gli errori del binario", () => {
  it.each([
    ["19.95", 1, "20,0"], ["19.9500", 1, "20,0"], [19.95, 1, "20,0"], ["8.45", 1, "8,5"], [8.45, 1, "8,5"], ["0.15", 1, "0,2"], [0.15, 1, "0,2"],
    ["1.25", 1, "1,3"], ["2.05", 1, "2,1"], ["10.8000", 1, "10,8"], ["10.84", 1, "10,8"], ["10.86", 1, "10,9"], ["0.04", 1, "0,0"],
    ["99.95", 1, "100,0"], ["999.95", 1, "1.000,0"], ["9.96", 1, "10,0"], ["1234.55", 1, "1.234,6"],
    ["2.345", 2, "2,35"], ["1.005", 2, "1,01"], ["7", 1, "7,0"], ["7.5", 0, "8"], ["7.4", 0, "7"], ["0.5", 0, "1"],
  ])("%s con %i decimali → %s", (value, digits, expected) => expect(roundHalfUp(value, digits)).toBe(expected));
  it("un valore non numerico non rompe la schermata", () => {
    expect(roundHalfUp("abc", 1)).toBe("—");
  });
  it("tutte le celle del carico usano questo arrotondamento", () => {
    expect(formatLoadCell("both", { fte: "0.9500", days: "19.9500", hours: "159.6", overloaded: false }).secondary).toBe("20,0 gg");
    expect(formatLoadCell("days", { fte: "0.4200", days: "8.4500", hours: "67.6", overloaded: false }).primary).toBe("8,5");
  });
});
