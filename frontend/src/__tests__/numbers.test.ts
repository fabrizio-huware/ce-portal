import { numberError, parseNumber, showNumber } from "../editor/numbers";

describe("parseNumber", () => {
  it.each([
    ["12", "12"], ["12,5", "12.5"], ["12.5", "12.5"], ["0,25", "0.25"], [".5", "0.5"], ["5.", "5"], [" 7 ", "7"], ["1 000", "1000"],
    ["1.234,5", "1234.5"], ["1.234", "1234"], ["12.345.678", "12345678"], ["50%", "50"], ["0", "0"], ["", ""], ["   ", ""],
  ])("%j -> %j", (input, expected) => expect(parseNumber(input)).toBe(expected));

  it.each(["abc", "1,2,3", "1.2.3", "-5", "1e5", "12a", "€10", ",", "."])("%j non è un numero", (input) => expect(parseNumber(input)).toBeNull());
});

describe("numberError", () => {
  it("campo vuoto: nessun errore (facoltativo o automatico)", () => expect(numberError("")).toBeNull());
  it("numero non valido", () => expect(numberError("dieci")).toBe("Inserisci un numero"));
  it("decimali", () => {
    expect(numberError("12,25")).toBeNull();
    expect(numberError("12,255")).toBe("Al massimo 2 decimali");
    expect(numberError("5,5", { integer: true })).toBe("Solo numeri interi");
    expect(numberError("23", { integer: true, max: 23 })).toBeNull();
  });
  it("massimo", () => {
    expect(numberError("100", { max: 100 })).toBeNull();
    expect(numberError("100,01", { max: 100 })).toBe("Al massimo 100");
  });
});

describe("showNumber", () => {
  it("mostra la virgola decimale", () => {
    expect(showNumber("12.5")).toBe("12,5");
    expect(showNumber(null)).toBe("");
    expect(showNumber(undefined)).toBe("");
  });
});
