import { profileForEmployee, type EmployeeOption, type ProfileOption } from "../editor/employeeProfile";

const profiles: ProfileOption[] = [
  { id: "partner", name: "Partner", rates: [{ year: 2026 }, { year: 2027 }] },
  { id: "manager", name: "Manager", rates: [{ year: 2026 }] },
  { id: "senior", name: "Senior", rates: [{ year: 2026 }] },
  { id: "nuovo", name: "Principal", rates: [{ year: 2027 }] }, // senza tariffa 2026
];
const rufini: EmployeeOption = { id: "e1", first_name: "Alessandro", last_name: "Rufini", default_profile_id: "partner" };
const clerici: EmployeeOption = { id: "e2", first_name: "Fabrizio", last_name: "Clerici", default_profile_id: "manager" };
const nuova: EmployeeOption = { id: "e3", first_name: "Giulia", last_name: "Neri", default_profile_id: "nuovo" };
const fantasma: EmployeeOption = { id: "e4", first_name: "Luca", last_name: "Bruno", default_profile_id: "disattivato" };

describe("profileForEmployee: il profilo segue il collaboratore", () => {
  it("riga senza profilo: si carica quello di default del collaboratore", () => {
    expect(profileForEmployee("", rufini, profiles, 2026)).toEqual({ profileId: "partner", unavailable: null });
  });
  it("segue SEMPRE il collaboratore, anche se la riga aveva un altro profilo scelto a mano", () => {
    expect(profileForEmployee("senior", rufini, profiles, 2026)).toEqual({ profileId: "partner", unavailable: null });
  });
  it("cambiando collaboratore su una riga che ne ha già uno, il profilo passa a quello del nuovo", () => {
    const first = profileForEmployee("", rufini, profiles, 2026);
    const second = profileForEmployee(first.profileId, clerici, profiles, 2026);
    expect(second).toEqual({ profileId: "manager", unavailable: null });
  });
  it("togliendo il collaboratore il profilo non cambia (e non resta nessuna nota)", () => {
    expect(profileForEmployee("partner", undefined, profiles, 2026)).toEqual({ profileId: "partner", unavailable: null });
    expect(profileForEmployee("", undefined, profiles, 2026)).toEqual({ profileId: "", unavailable: null });
  });
  it("la tariffa conta per l'anno del CE: lo stesso collaboratore con un altro anno", () => {
    expect(profileForEmployee("", rufini, profiles, 2027).profileId).toBe("partner");
    expect(profileForEmployee("senior", clerici, profiles, 2027)).toMatchObject({ profileId: "senior" }); // Manager non ha la tariffa 2027
  });
});

describe("profileForEmployee: quando il profilo di default non si può usare", () => {
  it("senza tariffa per l'anno: la riga conserva il suo profilo e c'è una nota col nome e l'anno", () => {
    const r = profileForEmployee("senior", nuova, profiles, 2026);
    expect(r.profileId).toBe("senior");
    expect(r.unavailable).toBe("Il profilo di default di Neri Giulia (Principal) non ha la tariffa 2026: scegli il profilo.");
  });
  it("senza tariffa e senza profilo sulla riga: resta vuoto (si dovrà scegliere) con la nota", () => {
    expect(profileForEmployee("", nuova, profiles, 2026)).toMatchObject({ profileId: "" });
    expect(profileForEmployee("", nuova, profiles, 2026).unavailable).toContain("Principal");
  });
  it("profilo di default non presente nell'elenco (disattivato): conserva il profilo e lo dice", () => {
    const r = profileForEmployee("manager", fantasma, profiles, 2026);
    expect(r).toEqual({ profileId: "manager", unavailable: "Il profilo di default di Bruno Luca non è disponibile: scegli il profilo." });
  });
  it("elenco profili vuoto (ancora in caricamento): non rompe e non imposta nulla", () => {
    expect(profileForEmployee("senior", rufini, [], 2026)).toMatchObject({ profileId: "senior" });
  });
  it("il nome nella nota è «Cognome Nome», come nel menu dei collaboratori", () => {
    expect(profileForEmployee("", nuova, profiles, 2026).unavailable).toMatch(/^Il profilo di default di Neri Giulia /);
  });
});
