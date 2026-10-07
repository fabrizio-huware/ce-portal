import type { CeDetail } from "../api/types";
import {
  addLine, addMilestone, addPhase, applyPaste, contentKey, draftFromDetail, duplicateLine, isDirty, isGridPaste, localIssues,
  monthsBetween, moveLine, movePhase, parseClipboard, removeLine, removeMilestone, removePhase, setHeader, toContent, updateLine,
  updateMilestone, updatePhase,
} from "../editor/model";

const detail = (mode: "hours" | "percent" = "hours"): CeDetail =>
  ({
    header: {
      client: { id: "c1", name: "Alfa" }, project_name: "Progetto", start_date: "2026-01-20", end_date: "2026-04-20", planning_mode: mode,
      sf_opportunity: "006X", business_unit: null, notes: null, max_discount_pct: "10.00", signed_price: null,
    },
    calculation: { months: ["2026-01-01", "2026-02-01", "2026-03-01", "2026-04-01"].map((month, i) => ({ month, weekdays: 20, non_working: i === 0 ? 5 : 0, work_days: 15 })) },
    phases: [
      {
        id: "p1", name: "Analysis", contingency_pct: "10.00",
        lines: [
          { id: "l1", activity: "Interviste", profile_id: "pr1", employee_id: "e1", is_project_management: false, hours: mode === "hours" ? "24.00" : null,
            allocations: mode === "percent" ? [{ month: "2026-01-01", pct: "50.00" }, { month: "2026-02-01", pct: "25.50" }] : [] },
          { id: "l2", activity: "Report", profile_id: "pr2", employee_id: null, is_project_management: true, hours: mode === "hours" ? "12.50" : null, allocations: [] },
        ],
      },
      { id: "p2", name: "Testing", contingency_pct: "0.00", lines: [] },
    ],
    milestones: [{ month: "2026-04-01", label: "Go live" }],
  }) as unknown as CeDetail;

describe("monthsBetween", () => {
  it("elenca i mesi, estremi inclusi", () => {
    expect(monthsBetween("2026-01-20", "2026-04-20")).toEqual(["2026-01-01", "2026-02-01", "2026-03-01", "2026-04-01"]);
    expect(monthsBetween("2026-11-30", "2027-02-01")).toEqual(["2026-11-01", "2026-12-01", "2027-01-01", "2027-02-01"]);
    expect(monthsBetween("2026-05-03", "2026-05-29")).toEqual(["2026-05-01"]);
  });
  it("date non valide o invertite: nessun mese", () => {
    expect(monthsBetween("", "2026-01-01")).toEqual([]);
    expect(monthsBetween("2026-05-01", "2026-04-01")).toEqual([]);
    expect(monthsBetween("2026-13-01", "2026-14-01")).toEqual([]);
  });
});

const toPercent_back = (d: ReturnType<typeof draftFromDetail>) => setHeader(d, { mode: "percent" });

describe("da API a bozza e ritorno", () => {
  it("modalità ore: i valori fanno il giro completo senza perdite", () => {
    const content = toContent(draftFromDetail(detail()), 7);
    expect(content).toEqual({
      expected_revision: 7,
      header: {
        client_id: "c1", project_name: "Progetto", start_date: "2026-01-20", end_date: "2026-04-20", planning_mode: "hours",
        sf_opportunity: "006X", business_unit: null, notes: null, max_discount_pct: "10", signed_price: null,
      },
      non_working_days: [
        { month: "2026-01-01", non_working_days: 5 }, { month: "2026-02-01", non_working_days: 0 },
        { month: "2026-03-01", non_working_days: 0 }, { month: "2026-04-01", non_working_days: 0 },
      ],
      phases: [
        { name: "Analysis", contingency_pct: "10", lines: [
          { activity: "Interviste", profile_id: "pr1", employee_id: "e1", is_project_management: false, hours: "24", allocations: [] },
          { activity: "Report", profile_id: "pr2", employee_id: null, is_project_management: true, hours: "12.5", allocations: [] },
        ] },
        { name: "Testing", contingency_pct: "0", lines: [] },
      ],
      milestones: [{ month: "2026-04-01", label: "Go live" }],
    });
  });
  it("modalità percentuali: le % mensili si conservano e le ore non si inviano", () => {
    const content = toContent(draftFromDetail(detail("percent")));
    expect(content.expected_revision).toBeUndefined();
    expect(content.phases[0].lines![0]).toMatchObject({ hours: null, allocations: [{ month: "2026-01-01", pct: "50" }, { month: "2026-02-01", pct: "25.5" }] });
    expect(content.phases[0].lines![1].allocations).toEqual([]);
  });
  it("cambiando modalità si inviano solo i dati della modalità scelta (gli altri restano in bozza, non si perdono)", () => {
    const hours = draftFromDetail(detail("hours")); // righe con ore
    const toPercent = toContent(setHeader(hours, { mode: "percent" }));
    expect(toPercent.phases[0].lines![0]).toMatchObject({ hours: null, allocations: [] });
    expect(toContent(setHeader(toPercent_back(hours), { mode: "hours" })).phases[0].lines![0].hours).toBe("24"); // tornando indietro le ore ci sono ancora
    const percent = draftFromDetail(detail("percent")); // righe con percentuali
    const toHours = toContent(setHeader(percent, { mode: "hours" }));
    expect(toHours.phases[0].lines![0].allocations).toEqual([]);
  });
  it("mostra i decimali con la virgola e lascia vuoti i valori a zero", () => {
    const d = draftFromDetail(detail());
    expect(d.phases[0].lines[1].hours).toBe("12,5");
    expect(d.phases[0].contingency).toBe("10");
    expect(d.phases[1].contingency).toBe("");
    expect(d.maxDiscount).toBe("10");
  });
  it("scrive i numeri con la virgola come l'API li vuole", () => {
    let d = draftFromDetail(detail());
    d = updateLine(d, "p1", "l1", { hours: "1.234,5" });
    d = setHeader(d, { maxDiscount: "7,5", signedPrice: "62.000,00" });
    const c = toContent(d);
    expect(c.phases[0].lines![0].hours).toBe("1234.5");
    expect(c.header.max_discount_pct).toBe("7.5");
    expect(c.header.signed_price).toBe("62000"); // numeri in forma canonica: senza zeri finali
  });
  it("ripulisce: spazi, note vuote, milestone senza testo, mesi fuori periodo", () => {
    let d = draftFromDetail(detail("percent"));
    d = setHeader(d, { projectName: "  Progetto  ", notes: "   " });
    d = updateLine(d, "p1", "l1", { alloc: { "2026-01-01": "10", "2027-05-01": "30", "2026-03-01": "" } });
    d = addMilestone(d, "2026-02-01");
    const c = toContent(d);
    expect(c.header.project_name).toBe("Progetto");
    expect(c.header.notes).toBeNull();
    expect(c.phases[0].lines![0].allocations).toEqual([{ month: "2026-01-01", pct: "10" }]);
    expect(c.milestones).toEqual([{ month: "2026-04-01", label: "Go live" }]);
  });
  it("giorni non lavorativi vuoti = automatici (non si inviano)", () => {
    const d = draftFromDetail(detail());
    const edited = { ...d, nonWorking: { ...d.nonWorking, "2026-02-01": "" } };
    expect(toContent(edited).non_working_days.map((m) => m.month)).not.toContain("2026-02-01");
  });
});

describe("modifiche non salvate", () => {
  it("si accorge di una modifica e anche del suo annullamento", () => {
    const d = draftFromDetail(detail());
    const baseline = contentKey(d);
    expect(isDirty(d, baseline)).toBe(false);
    const edited = updateLine(d, "p1", "l1", { hours: "30" });
    expect(isDirty(edited, baseline)).toBe(true);
    expect(isDirty(updateLine(edited, "p1", "l1", { hours: "24" }), baseline)).toBe(false);
  });
  it("le chiavi interne e la formattazione dei numeri non contano", () => {
    const d = draftFromDetail(detail());
    expect(isDirty(updateLine(d, "p1", "l1", { hours: "24,00" }), contentKey(d))).toBe(false);
  });
});

describe("controlli immediati", () => {
  const base = () => draftFromDetail(detail());
  const ids = (d = base()) => localIssues(d).map((i) => i.id);
  it("un CE completo non ha problemi", () => expect(localIssues(base())).toEqual([]));
  it("campi obbligatori", () => {
    const d = setHeader(base(), { clientId: "", projectName: " " });
    expect(ids(d)).toEqual(expect.arrayContaining(["clientId", "projectName"]));
  });
  it("periodo", () => {
    expect(ids(setHeader(base(), { endDate: "2025-01-01" }))).toContain("period");
    expect(ids(setHeader(base(), { endDate: "2027-06-01" }))).toContain("period"); // oltre 12 mesi
    expect(localIssues(setHeader(base(), { endDate: "2027-06-01" }))[0].message).toMatch(/12 mesi/);
  });
  it("righe e fasi incomplete, con la posizione nel messaggio", () => {
    let d = updateLine(base(), "p1", "l1", { activity: "", profileId: "" });
    d = updatePhase(d, "p2", { name: "" });
    const messages = localIssues(d).map((i) => i.message);
    expect(messages).toContain("Analysis, riga 1: manca l'attività");
    expect(messages).toContain("Analysis, riga 1: scegli il profilo");
    expect(messages).toContain("La fase 2 non ha un nome");
  });
  it("numeri non validi", () => {
    let d = updateLine(base(), "p1", "l1", { hours: "tanto" });
    d = updatePhase(d, "p1", { contingency: "150" });
    d = setHeader(d, { maxDiscount: "x" });
    expect(ids(d)).toEqual(expect.arrayContaining(["hours-l1", "cont-p1", "Max sconto"]));
  });
  it("percentuali non valide in modalità percentuali (e le ore non contano)", () => {
    const d = draftFromDetail(detail("percent"));
    expect(ids(updateLine(d, "p1", "l1", { alloc: { "2026-01-01": "120" } }))).toContain("alloc-l1-2026-01-01");
    expect(ids(updateLine(base(), "p1", "l1", { alloc: { "2026-01-01": "120" } }))).not.toContain("alloc-l1-2026-01-01");
  });
});

describe("operazioni su fasi e righe", () => {
  const base = () => draftFromDetail(detail());
  it("aggiunge, sposta e toglie fasi (senza uscire dai limiti)", () => {
    let d = addPhase(base(), "Delivery");
    expect(d.phases.map((p) => p.name)).toEqual(["Analysis", "Testing", "Delivery"]);
    d = movePhase(d, "p2", -1);
    expect(d.phases.map((p) => p.name)).toEqual(["Testing", "Analysis", "Delivery"]);
    expect(movePhase(d, d.phases[0].key, -1)).toBe(d); // già in cima: nessun cambiamento
    expect(movePhase(d, d.phases[2].key, 1)).toBe(d);
    expect(removePhase(d, "p2").phases.map((p) => p.name)).toEqual(["Analysis", "Delivery"]);
  });
  it("una riga nuova riprende il profilo dell'ultima", () => {
    const d = addLine(base(), "p1");
    expect(d.phases[0].lines).toHaveLength(3);
    expect(d.phases[0].lines[2]).toMatchObject({ profileId: "pr2", activity: "", hours: "", employeeId: "" });
    expect(addLine(base(), "p2").phases[1].lines[0].profileId).toBe("");
  });
  it("sposta, duplica e toglie righe", () => {
    let d = moveLine(base(), "p1", "l2", -1);
    expect(d.phases[0].lines.map((l) => l.key)).toEqual(["l2", "l1"]);
    expect(moveLine(d, "p1", "l2", -1)).toEqual(d);
    d = duplicateLine(base(), "p1", "l1");
    expect(d.phases[0].lines.map((l) => l.activity)).toEqual(["Interviste", "Interviste", "Report"]);
    expect(new Set(d.phases[0].lines.map((l) => l.key)).size).toBe(3);
    expect(removeLine(d, "p1", "l2").phases[0].lines).toHaveLength(2);
  });
  it("le copie non condividono le percentuali con l'originale", () => {
    const d = duplicateLine(draftFromDetail(detail("percent")), "p1", "l1");
    const edited = updateLine(d, "p1", d.phases[0].lines[1].key, { alloc: { "2026-01-01": "99" } });
    expect(edited.phases[0].lines[0].alloc["2026-01-01"]).toBe("50");
  });
  it("non modifica mai la bozza di partenza", () => {
    const d = base();
    const snapshot = JSON.stringify(d);
    updateLine(d, "p1", "l1", { hours: "99" }); addPhase(d); removeLine(d, "p1", "l1"); movePhase(d, "p1", 1);
    expect(JSON.stringify(d)).toBe(snapshot);
  });
  it("milestone", () => {
    let d = addMilestone(base(), "2026-02-01");
    const key = d.milestones[1].key;
    d = updateMilestone(d, key, { label: "Kick-off" });
    expect(toContent(d).milestones).toEqual([{ month: "2026-04-01", label: "Go live" }, { month: "2026-02-01", label: "Kick-off" }]);
    expect(removeMilestone(d, key).milestones).toHaveLength(1);
  });
});

describe("incolla da Excel", () => {
  const months = ["2026-01-01", "2026-02-01", "2026-03-01", "2026-04-01"];
  const withLines = (mode: "hours" | "percent" = "hours") => {
    let d = draftFromDetail(detail(mode));
    d = addLine(d, "p1");
    return { d, keys: d.phases[0].lines.map((l) => l.key) };
  };
  it("riconosce un blocco di celle da un semplice testo", () => {
    expect(isGridPaste("12")).toBe(false);
    expect(isGridPaste("12\n")).toBe(false);
    expect(isGridPaste("12\n24")).toBe(true);
    expect(isGridPaste("10\t20")).toBe(true);
    expect(parseClipboard("1\t2\r\n3\t4\r\n")).toEqual([["1", "2"], ["3", "4"]]);
  });
  it("ore: una colonna riempie le righe successive e si ferma alla fine della fase", () => {
    const { d, keys } = withLines();
    const out = applyPaste(d, "p1", keys[1], "hours", "8\n16\n24\n32", months);
    expect(out.phases[0].lines.map((l) => l.hours)).toEqual(["24", "8", "16"]); // la prima riga non cambia; il resto non si perde né si crea
  });
  it("ore: formato italiano e simbolo %, con riga finale vuota di Excel", () => {
    const { d, keys } = withLines();
    const out = applyPaste(d, "p1", keys[0], "hours", "1.234,5\n12,25\n", months);
    expect(out.phases[0].lines.slice(0, 2).map((l) => l.hours)).toEqual(["1234,5", "12,25"]);
  });
  it("ore: un valore non numerico resta com'è, così si vede l'errore", () => {
    const { d, keys } = withLines();
    const out = applyPaste(d, "p1", keys[0], "hours", "n.d.\n8", months);
    expect(out.phases[0].lines[0].hours).toBe("n.d.");
    expect(localIssues(out).map((i) => i.id)).toContain(`hours-${keys[0]}`);
  });
  it("percentuali: un blocco righe x colonne riempie i mesi a partire dalla colonna scelta", () => {
    const { d, keys } = withLines("percent");
    const out = applyPaste(d, "p1", keys[1], "2026-02-01", "10\t20\t30\t40\n5%\t15%", months);
    expect(out.phases[0].lines[1].alloc).toMatchObject({ "2026-02-01": "10", "2026-03-01": "20", "2026-04-01": "30" });
    expect(out.phases[0].lines[1].alloc["2026-05-01"]).toBeUndefined(); // il quarto valore esce dal periodo
    expect(out.phases[0].lines[2].alloc).toMatchObject({ "2026-02-01": "5", "2026-03-01": "15" });
  });
  it("celle sconosciute: nessun cambiamento", () => {
    const { d, keys } = withLines();
    expect(applyPaste(d, "nessuna", keys[0], "hours", "1", months)).toBe(d);
    expect(applyPaste(d, "p1", "nessuna", "hours", "1", months)).toBe(d);
    expect(applyPaste(d, "p1", keys[0], "2030-01-01", "1", months)).toBe(d);
  });
});
