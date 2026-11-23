import { describe, expect, it } from "vitest";

import { parseYears } from "../components/admin/CopyRatesDialog";

describe("parseYears", () => {
  it("accetta uno o più anni separati da virgola, punto e virgola o spazio", () => {
    expect(parseYears("2027")).toEqual([2027]);
    expect(parseYears("2027, 2028")).toEqual([2027, 2028]);
    expect(parseYears("2027 2028;2029")).toEqual([2027, 2028, 2029]);
  });
  it("rifiuta vuoto, anni non validi, ripetuti o più di dieci", () => {
    expect(parseYears("")).toBeNull();
    expect(parseYears("  ")).toBeNull();
    expect(parseYears("27")).toBeNull();
    expect(parseYears("1999")).toBeNull();
    expect(parseYears("2101")).toBeNull();
    expect(parseYears("2027, abc")).toBeNull();
    expect(parseYears("2027, 2027")).toBeNull();
    expect(parseYears("2020 2021 2022 2023 2024 2025 2026 2027 2028 2029 2030")).toBeNull();
  });
});
