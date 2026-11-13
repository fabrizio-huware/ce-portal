import { choosablePractices, isSystemPractice, SYSTEM_PRACTICE } from "../lib/practice";

const list = [
  { id: "a", name: "Cloud", is_active: true },
  { id: "b", name: "Vecchia", is_active: false },
  { id: "c", name: "Data", is_active: true },
];

describe("choosablePractices", () => {
  it("offre le practice attive e non quelle disattivate", () => {
    expect(choosablePractices(list, "").map((p) => p.id)).toEqual(["a", "c"]);
  });
  it("tiene la practice che il collaboratore ha già, anche se disattivata", () => {
    expect(choosablePractices(list, "b").map((p) => p.id)).toEqual(["a", "b", "c"]);
  });
  it("una practice attiva già assegnata non compare due volte", () => {
    expect(choosablePractices(list, "a").map((p) => p.id)).toEqual(["a", "c"]);
  });
  it("un identificativo sconosciuto, o un elenco vuoto, non rompe nulla", () => {
    expect(choosablePractices(list, "zzz").map((p) => p.id)).toEqual(["a", "c"]);
    expect(choosablePractices([], "a")).toEqual([]);
  });
  it("conserva le altre proprietà dell'elemento", () => {
    const withCount = [{ id: "x", name: "Cloud", is_active: true, employees_count: 4 }];
    expect(choosablePractices(withCount, "")[0].employees_count).toBe(4);
  });
});

describe("practice di sistema", () => {
  it("è «Da assegnare», come nel backend", () => {
    expect(SYSTEM_PRACTICE).toBe("Da assegnare");
  });
  it("si riconosce senza badare a maiuscole e spazi", () => {
    for (const name of ["Da assegnare", "da assegnare", "DA ASSEGNARE", "  Da assegnare  "]) expect(isSystemPractice(name)).toBe(true);
  });
  it("le altre practice non sono di sistema", () => {
    for (const name of ["Data", "Da assegnare 2", "Assegnare", ""]) expect(isSystemPractice(name)).toBe(false);
  });
});
