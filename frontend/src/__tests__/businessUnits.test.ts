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

import { choosableForCe, toggleUnit, undeclaredUnits } from "../lib/businessUnits";

describe("toggleUnit", () => {
  it("aggiunge in coda, senza doppioni, e toglie", () => {
    expect(toggleUnit(["a"], "b", true)).toEqual(["a", "b"]);
    expect(toggleUnit(["a", "b"], "a", true)).toEqual(["b", "a"]);
    expect(toggleUnit(["a", "b"], "a", false)).toEqual(["b"]);
    expect(toggleUnit([], "x", false)).toEqual([]);
  });
});

describe("choosableForCe", () => {
  const list = [u("a", "Data & AI"), u("b", "Vecchia", false), u("s", "Da assegnare"), u("c", "Cloud")];
  it("offre le attive e vere, mai «Da assegnare»", () => {
    expect(choosableForCe(list, []).map((x) => x.id)).toEqual(["a", "c"]);
  });
  it("tiene quelle già coinvolte anche se disattivate, ma non quella di sistema se non c'è", () => {
    expect(choosableForCe(list, ["b"]).map((x) => x.id)).toEqual(["a", "b", "c"]);
  });
});

describe("undeclaredUnits", () => {
  const emps = [
    { id: "e1", business_unit_id: "a", business_unit_name: "Data & AI" },
    { id: "e2", business_unit_id: "c", business_unit_name: "Cloud" },
    { id: "e3", business_unit_id: "s", business_unit_name: "Da assegnare" },
    { id: "e4", business_unit_id: "d", business_unit_name: "Zeta" },
  ];
  it("segnala le business unit dei collaboratori delle righe non coinvolte, in ordine alfabetico", () => {
    expect(undeclaredUnits(["e4", "e2", "e1"], emps, ["a"])).toEqual([{ id: "c", name: "Cloud" }, { id: "d", name: "Zeta" }]);
  });
  it("non segnala quelle già coinvolte né «Da assegnare», e non duplica", () => {
    expect(undeclaredUnits(["e1", "e3"], emps, ["a"])).toEqual([]);
    expect(undeclaredUnits(["e2", "e2"], emps, [])).toEqual([{ id: "c", name: "Cloud" }]);
  });
  it("ignora i collaboratori non presenti in riga o sconosciuti", () => {
    expect(undeclaredUnits(["boh"], emps, [])).toEqual([]);
    expect(undeclaredUnits([], emps, [])).toEqual([]);
  });
});

import { visibilityWarnings } from "../lib/businessUnits";

describe("visibilityWarnings", () => {
  const none = { ces_without_business_units: 0, people_without_business_unit: [], practices_unassigned: 0 };
  it("è vuota se non manca nulla", () => {
    expect(visibilityWarnings(none)).toEqual([]);
  });
  it("dice quanti CE restano senza business unit, al singolare e al plurale", () => {
    expect(visibilityWarnings({ ...none, ces_without_business_units: 1 })[0]).toContain("1 CE non ha business unit: lo vedranno solo l'autore");
    expect(visibilityWarnings({ ...none, ces_without_business_units: 12 })[0]).toContain("12 CE non hanno business unit: li vedranno");
  });
  it("elenca i presale senza business unit, al massimo cinque nomi", () => {
    expect(visibilityWarnings({ ...none, people_without_business_unit: ["Anna Rossi"] })[0]).toBe("1 presale non ha business unit e vedrà solo i propri CE: Anna Rossi.");
    const many = ["A", "B", "C", "D", "E", "F", "G"];
    expect(visibilityWarnings({ ...none, people_without_business_unit: many })[0]).toContain("7 presale non hanno business unit e vedranno solo i propri CE: A, B, C, D, E e altri 2.");
  });
  it("segnala le practice ancora in «Da assegnare»", () => {
    expect(visibilityWarnings({ ...none, practices_unassigned: 2 })[0]).toBe("2 practice sono ancora in «Da assegnare»: i suoi collaboratori non appartengono a nessuna business unit.");
    expect(visibilityWarnings({ ...none, practices_unassigned: 1 })[0]).toContain("1 practice è ancora in");
  });
  it("mette insieme più avvisi, nell'ordine CE, persone, practice", () => {
    const w = visibilityWarnings({ ces_without_business_units: 3, people_without_business_unit: ["X"], practices_unassigned: 1 });
    expect(w).toHaveLength(3);
    expect(w[0]).toContain("CE"); expect(w[1]).toContain("presale"); expect(w[2]).toContain("practice");
  });
});
