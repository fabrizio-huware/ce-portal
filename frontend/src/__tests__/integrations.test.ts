import { isServiceAccountEmail, PERMISSIONS, permissionLabels, portalAudience, presaleChoices, togglePermission } from "../lib/integrations";

describe("isServiceAccountEmail", () => {
  it("accetta l'email di un account di servizio, anche con maiuscole e spazi", () => {
    for (const v of ["portale@progetto.iam.gserviceaccount.com", "  Portale-Esterno@Prog-1.iam.gserviceaccount.com ", "a.b_c@x.y.iam.gserviceaccount.com"]) expect(isServiceAccountEmail(v)).toBe(true);
  });
  it("rifiuta le persone e le altre email", () => {
    for (const v of ["", "anna@huware.com", "x@iam.gserviceaccount.com.evil.com", "senza-chiocciola.iam.gserviceaccount.com", "@p.iam.gserviceaccount.com", "a b@p.iam.gserviceaccount.com", "-x@p.iam.gserviceaccount.com"]) expect(isServiceAccountEmail(v)).toBe(false);
  });
  it("rifiuta indirizzi troppo lunghi", () => {
    expect(isServiceAccountEmail(`${"a".repeat(320)}@p.iam.gserviceaccount.com`)).toBe(false);
  });
});

describe("permessi", () => {
  it("sono quelli del server, nell'ordine canonico", () => {
    expect(PERMISSIONS.map((p) => p.key)).toEqual(["create", "edit", "read", "export"]);
    expect(new Set(PERMISSIONS.map((p) => p.label)).size).toBe(4);
  });
  it("togglePermission mantiene l'ordine e non crea doppioni", () => {
    expect(togglePermission(["read"], "create", true)).toEqual(["create", "read"]);
    expect(togglePermission(["create", "read"], "create", true)).toEqual(["create", "read"]);
    expect(togglePermission(["create", "edit", "read"], "edit", false)).toEqual(["create", "read"]);
    expect(togglePermission([], "export", false)).toEqual([]);
  });
  it("togglePermission scarta i permessi sconosciuti", () => {
    expect(togglePermission(["delete", "read"], "edit", true)).toEqual(["edit", "read"]);
  });
  it("permissionLabels dà le etichette brevi in ordine e ignora gli sconosciuti", () => {
    expect(permissionLabels(["export", "create", "boh"])).toEqual(["Creare", "PDF"]);
    expect(permissionLabels([])).toEqual([]);
  });
});

describe("portalAudience", () => {
  it("toglie la barra finale e gli spazi", () => {
    expect(portalAudience("https://ce.example.run.app/")).toBe("https://ce.example.run.app");
    expect(portalAudience(" https://ce.example.run.app ")).toBe("https://ce.example.run.app");
    expect(portalAudience("http://localhost:8000")).toBe("http://localhost:8000");
  });
});

describe("presaleChoices", () => {
  const u = (id: string, full_name: string, role: string, is_active = true) => ({ id, full_name, role, is_active });
  it("offre solo i presale attivi, in ordine alfabetico", () => {
    const out = presaleChoices([u("1", "Zeno", "presale"), u("2", "Anna", "presale"), u("3", "Mario", "admin"), u("4", "Vera", "viewer"), u("5", "Bruno", "presale", false), u("6", "élodie", "presale")]);
    expect(out.map((p) => p.id)).toEqual(["2", "6", "1"]);
  });
  it("con un elenco vuoto non rompe nulla", () => {
    expect(presaleChoices([])).toEqual([]);
  });
});

import { HISTORY_LABEL, historyDetail } from "../lib/status";

describe("cronologia: assegnazione e creazione da integrazione", () => {
  it("le due azioni nuove hanno un'etichetta leggibile", () => {
    expect(HISTORY_LABEL.assign).toBe("Assegnato a un presale");
    expect(HISTORY_LABEL.create_by_integration).toBe("Creato da un'integrazione");
  });
  it("historyDetail dice a chi è stato assegnato e con quale riferimento è nato", () => {
    expect(historyDetail("assign", { from: "Portale esterno (servizio)", to: "Anna Presale" })).toBe("a Anna Presale");
    expect(historyDetail("create_by_integration", { integration: "P", external_ref: "EXT-001" })).toBe("rif. EXT-001");
  });
  it("senza dati o per altre azioni non inventa nulla", () => {
    for (const changes of [null, undefined, {}, "x", { to: "" }, { to: 3 }]) expect(historyDetail("assign", changes)).toBeNull();
    expect(historyDetail("create_by_integration", {})).toBeNull();
    expect(historyDetail("approve", { to: "Anna" })).toBeNull();
  });
});

describe("cronologia: business unit coinvolte", () => {
  it("dice da quali a quali business unit si è passati", () => {
    expect(HISTORY_LABEL.set_business_units).toBe("Business unit coinvolte cambiate");
    expect(historyDetail("set_business_units", { from: ["Cloud"], to: ["Cloud", "Data & AI"] })).toBe("da Cloud a Cloud, Data & AI");
    expect(historyDetail("set_business_units", { from: [], to: ["Data & AI"] })).toBe("da nessuna a Data & AI");
  });
  it("senza business unit di arrivo o con dati strani non inventa nulla", () => {
    for (const changes of [null, {}, { from: ["A"], to: [] }, { from: "A", to: "B" }]) expect(historyDetail("set_business_units", changes)).toBeNull();
  });
});
