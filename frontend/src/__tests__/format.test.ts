import { date, datetime, money, month, num, pct, period, points } from "../lib/format";

describe("formati italiani", () => {
  it("numeri con migliaia e virgola decimale", () => {
    expect(num("1234567.5")).toBe("1.234.567,50");
    expect(num(0)).toBe("0,00");
    expect(num("999.999")).toBe("1.000,00");
    expect(num("12.3456", 4)).toBe("12,3456");
    expect(num(1234, 0)).toBe("1.234");
  });
  it("numeri negativi e zero negativo", () => {
    expect(num(-1234.5)).toBe("-1.234,50");
    expect(num(-0.001)).toBe("0,00"); // niente "-0,00"
  });
  it("valori mancanti o non numerici", () => {
    for (const v of [null, undefined, "", "abc", NaN]) expect(num(v as never)).toBe("—");
    expect(money(null)).toBe("—");
  });
  it("importi, percentuali e punti", () => {
    expect(money("47162.5")).toBe("47.162,50 €");
    expect(pct("0.571694")).toBe("57,17%");
    expect(pct(0)).toBe("0,00%");
    expect(pct(null)).toBe("n/d");
    expect(pct("0.4", 0)).toBe("40%");
    expect(points("10")).toBe("10,00%");
    expect(points(null)).toBe("—");
  });
  it("date senza spostamenti di fuso orario", () => {
    expect(date("2026-01-05")).toBe("05/01/2026");
    expect(date("2026-12-31T23:59:59Z")).toBe("31/12/2026");
    expect(date(null)).toBe("—");
    expect(month("2026-03-01")).toBe("mar 2026");
    expect(period("2026-01-20", "2026-04-20")).toBe("20/01/2026 – 20/04/2026");
  });
  it("data e ora in ora italiana (legale e solare)", () => {
    expect(datetime("2026-10-06T12:30:00Z")).toBe("06/10/2026 14:30");
    expect(datetime("2026-01-06T12:30:00Z")).toBe("06/01/2026 13:30");
    expect(datetime("2026-12-31T23:30:00Z")).toBe("01/01/2027 00:30");
    expect(datetime(undefined)).toBe("—");
  });
});
