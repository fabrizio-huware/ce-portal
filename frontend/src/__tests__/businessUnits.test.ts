import { canHaveBusinessUnit, choosableBusinessUnits, isSystemBusinessUnit, roleNeedsBusinessUnit, SYSTEM_BUSINESS_UNIT } from "../lib/businessUnits";

const u = (id: string, name: string, is_active = true) => ({ id, name, is_active });

describe("business unit di sistema", () => {
  it("è «Da assegnare», come nel backend", () => {
    expect(SYSTEM_BUSINESS_UNIT).toBe("Da assegnare");
  });
  it("si riconosce senza badare a maiuscole e spazi", () => {
    for (const n of ["Da assegnare", "da assegnare", "  DA ASSEGNARE "]) expect(isSystemBusinessUnit(n)).toBe(true);
    for (const n of ["Data & AI", "Da assegnare 2", ""]) expect(isSystemBusinessUnit(n)).toBe(false);
  });
});

describe("choosableBusinessUnits", () => {
  const list = [u("a", "Data & AI"), u("b", "Vecchia", false), u("s", "Da assegnare"), u("c", "Cloud")];
  it("per le practice offre le attive, «Da assegnare» compresa", () => {
    expect(choosableBusinessUnits(list, "", false).map((x) => x.id)).toEqual(["a", "s", "c"]);
  });
  it("per le persone toglie «Da assegnare»", () => {
    expect(choosableBusinessUnits(list, "", true).map((x) => x.id)).toEqual(["a", "c"]);
  });
  it("tiene quella già assegnata, anche se disattivata", () => {
    expect(choosableBusinessUnits(list, "b", true).map((x) => x.id)).toEqual(["a", "b", "c"]);
    expect(choosableBusinessUnits(list, "b", false).map((x) => x.id)).toEqual(["a", "b", "s", "c"]);
  });
  it("con un elenco vuoto o un identificativo sconosciuto non rompe nulla", () => {
    expect(choosableBusinessUnits([], "x", true)).toEqual([]);
    expect(choosableBusinessUnits(list, "zzz", true).map((x) => x.id)).toEqual(["a", "c"]);
  });
});

describe("ruoli e business unit", () => {
  it("la hanno solo presale e responsabili", () => {
    expect(["presale", "bu_manager"].every(canHaveBusinessUnit)).toBe(true);
    expect(["admin", "viewer", ""].some(canHaveBusinessUnit)).toBe(false);
  });
  it("è obbligatoria solo per il responsabile", () => {
    expect(roleNeedsBusinessUnit("bu_manager")).toBe(true);
    expect(["presale", "admin", "viewer"].some(roleNeedsBusinessUnit)).toBe(false);
  });
});
