/**
 * Modello dell'editor: la "bozza" che l'utente modifica, le sue conversioni da e verso l'API e le
 * operazioni su fasi e righe. Tutto qui è puro (nessun React), così si prova facilmente.
 *
 * Il calcolo dei totali NON si rifà nel browser: lo fa il server (`POST /ce/{id}/calculate`) con lo
 * stesso motore usato per salvare, così i numeri sono sempre identici.
 */
import type { components } from "../api/schema";
import type { CeDetail } from "../api/types";
import { numberError, parseNumber, showNumber } from "./numbers";

type ContentSchema = components["schemas"]["ContentIn"];
/** Contenuto da inviare: fasi, mesi e milestone sono sempre presenti. */
export type ContentIn = ContentSchema & Required<Pick<ContentSchema, "phases" | "non_working_days" | "milestones">>;

export type LineDraft = {
  key: string;
  activity: string;
  profileId: string;
  employeeId: string; // "" = nessun collaboratore
  isPm: boolean;
  hours: string; // modalità ore
  alloc: Record<string, string>; // modalità percentuali: mese (AAAA-MM-01) -> %
};
export type PhaseDraft = { key: string; name: string; contingency: string; lines: LineDraft[] };
export type MilestoneDraft = { key: string; month: string; label: string };
export type Draft = {
  clientId: string;
  projectName: string;
  startDate: string;
  endDate: string;
  mode: "hours" | "percent";
  salesforce: string;
  businessUnit: string;
  notes: string;
  maxDiscount: string;
  signedPrice: string;
  nonWorking: Record<string, string>; // mese -> giorni non lavorativi ("" = automatico dal calendario)
  phases: PhaseDraft[];
  milestones: MilestoneDraft[];
};

let counter = 0;
export const newKey = (): string => `k${++counter}`;

// ---------------------------------------------------------------- mesi
/** Primi giorni dei mesi compresi tra due date (estremi inclusi). Vuoto se le date non sono valide. */
export function monthsBetween(start: string, end: string): string[] {
  const ok = (s: string) => /^\d{4}-\d{2}-\d{2}$/.test(s) && !Number.isNaN(Date.parse(s));
  if (!ok(start) || !ok(end) || end < start) return [];
  let y = Number(start.slice(0, 4));
  let m = Number(start.slice(5, 7));
  const ey = Number(end.slice(0, 4));
  const em = Number(end.slice(5, 7));
  const out: string[] = [];
  while (y < ey || (y === ey && m <= em)) {
    out.push(`${y}-${String(m).padStart(2, "0")}-01`);
    if (++m > 12) {
      m = 1;
      y++;
    }
    if (out.length > 60) break;
  }
  return out;
}

// ---------------------------------------------------------------- da API a bozza
export function emptyLine(profileId = ""): LineDraft {
  return { key: newKey(), activity: "", profileId, employeeId: "", isPm: false, hours: "", alloc: {} };
}

export function draftFromDetail(detail: CeDetail): Draft {
  const h = detail.header;
  return {
    clientId: h.client.id,
    projectName: h.project_name,
    startDate: h.start_date,
    endDate: h.end_date,
    mode: h.planning_mode,
    salesforce: h.sf_opportunity ?? "",
    businessUnit: h.business_unit ?? "",
    notes: h.notes ?? "",
    maxDiscount: Number(h.max_discount_pct) === 0 ? "" : showNumber(trimZeros(h.max_discount_pct)),
    signedPrice: h.signed_price === null || h.signed_price === undefined ? "" : showNumber(trimZeros(h.signed_price)),
    nonWorking: Object.fromEntries(detail.calculation.months.map((m) => [m.month, String(m.non_working)])),
    phases: detail.phases.map((p) => ({
      key: p.id,
      name: p.name,
      contingency: Number(p.contingency_pct) === 0 ? "" : showNumber(trimZeros(p.contingency_pct)),
      lines: p.lines.map((l) => ({
        key: l.id,
        activity: l.activity,
        profileId: l.profile_id,
        employeeId: l.employee_id ?? "",
        isPm: l.is_project_management,
        hours: l.hours === null || l.hours === undefined ? "" : showNumber(trimZeros(l.hours)),
        alloc: Object.fromEntries(l.allocations.map((a) => [a.month, showNumber(trimZeros(a.pct))])),
      })),
    })),
    milestones: detail.milestones.map((m) => ({ key: newKey(), month: m.month, label: m.label })),
  };
}

/** "24.00" -> "24"; "12.50" -> "12.5" */
function trimZeros(v: string): string {
  return v.includes(".") ? v.replace(/0+$/, "").replace(/\.$/, "") : v;
}

// ---------------------------------------------------------------- da bozza ad API
const num = (text: string): string | null => {
  const n = parseNumber(text);
  return n === "" || n === null ? null : trimZeros(n);
};

export function toContent(d: Draft, revision?: number): ContentIn {
  const months = monthsBetween(d.startDate, d.endDate);
  return {
    ...(revision !== undefined && { expected_revision: revision }),
    header: {
      client_id: d.clientId,
      project_name: d.projectName.trim(),
      start_date: d.startDate,
      end_date: d.endDate,
      planning_mode: d.mode,
      sf_opportunity: d.salesforce.trim() || null,
      business_unit: d.businessUnit.trim() || null,
      notes: d.notes.trim() || null,
      max_discount_pct: num(d.maxDiscount) ?? "0",
      signed_price: num(d.signedPrice),
    },
    non_working_days: months
      .filter((m) => (d.nonWorking[m] ?? "").trim() !== "")
      .map((m) => ({ month: m, non_working_days: Number(d.nonWorking[m]) })),
    phases: d.phases.map((p) => ({
      name: p.name.trim(),
      contingency_pct: num(p.contingency) ?? "0",
      lines: p.lines.map((l) => ({
        activity: l.activity.trim(),
        profile_id: l.profileId,
        employee_id: l.employeeId || null,
        is_project_management: l.isPm,
        hours: d.mode === "hours" ? num(l.hours) : null,
        allocations:
          d.mode === "percent"
            ? months.filter((m) => num(l.alloc[m] ?? "") !== null).map((m) => ({ month: m, pct: num(l.alloc[m])! }))
            : [],
      })),
    })),
    milestones: d.milestones.filter((m) => m.label.trim()).map((m) => ({ month: m.month, label: m.label.trim() })),
  };
}

export const contentKey = (d: Draft): string => JSON.stringify(toContent(d));
export const isDirty = (d: Draft, baseline: string): boolean => contentKey(d) !== baseline;

// ---------------------------------------------------------------- controlli immediati (la validazione definitiva è del server)
export type Issue = { id: string; message: string };

export function localIssues(d: Draft): Issue[] {
  const out: Issue[] = [];
  if (!d.clientId) out.push({ id: "clientId", message: "Scegli il cliente" });
  if (!d.projectName.trim()) out.push({ id: "projectName", message: "Indica il nome del progetto" });
  if (!d.startDate || !d.endDate) out.push({ id: "period", message: "Indica le date di inizio e fine" });
  else if (d.endDate < d.startDate) out.push({ id: "period", message: "La data di fine precede quella di inizio" });
  else if (monthsBetween(d.startDate, d.endDate).length > 12) out.push({ id: "period", message: "Il periodo non può superare 12 mesi" });
  const rules: [string, string, Parameters<typeof numberError>[1]][] = [
    ["Max sconto", d.maxDiscount, { max: 100 }],
    ["Prezzo firmato", d.signedPrice, {}],
  ];
  for (const [label, value, rule] of rules) {
    const e = numberError(value, rule);
    if (e) out.push({ id: label, message: `${label}: ${e.toLowerCase()}` });
  }
  d.phases.forEach((p, i) => {
    if (!p.name.trim()) out.push({ id: `phase-${p.key}`, message: `La fase ${i + 1} non ha un nome` });
    const ce = numberError(p.contingency, { max: 100 });
    if (ce) out.push({ id: `cont-${p.key}`, message: `Contingency di «${p.name || `fase ${i + 1}`}»: ${ce.toLowerCase()}` });
    p.lines.forEach((l, j) => {
      const where = `${p.name || `Fase ${i + 1}`}, riga ${j + 1}`;
      if (!l.activity.trim()) out.push({ id: `act-${l.key}`, message: `${where}: manca l'attività` });
      if (!l.profileId) out.push({ id: `prof-${l.key}`, message: `${where}: scegli il profilo` });
      const he = d.mode === "hours" ? numberError(l.hours, { decimals: 2 }) : null;
      if (he) out.push({ id: `hours-${l.key}`, message: `${where}: ore, ${he.toLowerCase()}` });
      if (d.mode === "percent") {
        for (const [m, v] of Object.entries(l.alloc)) {
          const pe = numberError(v, { max: 100 });
          if (pe) out.push({ id: `alloc-${l.key}-${m}`, message: `${where}: percentuale, ${pe.toLowerCase()}` });
        }
      }
    });
  });
  for (const [m, v] of Object.entries(d.nonWorking)) {
    const e = numberError(v, { integer: true, max: 23 });
    if (e) out.push({ id: `nw-${m}`, message: `Giorni non lavorativi: ${e.toLowerCase()}` });
  }
  return out;
}

// ---------------------------------------------------------------- operazioni su fasi e righe
const swap = <T,>(arr: T[], i: number, j: number): T[] => {
  if (j < 0 || j >= arr.length) return arr;
  const copy = arr.slice();
  [copy[i], copy[j]] = [copy[j], copy[i]];
  return copy;
};

export const setHeader = (d: Draft, patch: Partial<Draft>): Draft => ({ ...d, ...patch });

export const addPhase = (d: Draft, name = ""): Draft => ({
  ...d,
  phases: [...d.phases, { key: newKey(), name, contingency: "", lines: [] }],
});
export const removePhase = (d: Draft, key: string): Draft => ({ ...d, phases: d.phases.filter((p) => p.key !== key) });
export const movePhase = (d: Draft, key: string, dir: -1 | 1): Draft => {
  const i = d.phases.findIndex((p) => p.key === key);
  if (i < 0) return d;
  const phases = swap(d.phases, i, i + dir);
  return phases === d.phases ? d : { ...d, phases };
};
export const updatePhase = (d: Draft, key: string, patch: Partial<Omit<PhaseDraft, "key" | "lines">>): Draft => ({
  ...d,
  phases: d.phases.map((p) => (p.key === key ? { ...p, ...patch } : p)),
});

const mapPhase = (d: Draft, key: string, fn: (p: PhaseDraft) => PhaseDraft): Draft => ({
  ...d,
  phases: d.phases.map((p) => (p.key === key ? fn(p) : p)),
});

/** Una nuova riga riprende il profilo dell'ultima della fase: di solito si inseriscono righe simili. */
export const addLine = (d: Draft, phaseKey: string): Draft =>
  mapPhase(d, phaseKey, (p) => ({ ...p, lines: [...p.lines, emptyLine(p.lines.at(-1)?.profileId ?? "")] }));
export const removeLine = (d: Draft, phaseKey: string, lineKey: string): Draft =>
  mapPhase(d, phaseKey, (p) => ({ ...p, lines: p.lines.filter((l) => l.key !== lineKey) }));
export const moveLine = (d: Draft, phaseKey: string, lineKey: string, dir: -1 | 1): Draft =>
  mapPhase(d, phaseKey, (p) => {
    const i = p.lines.findIndex((l) => l.key === lineKey);
    if (i < 0) return p;
    const lines = swap(p.lines, i, i + dir);
    return lines === p.lines ? p : { ...p, lines };
  });
export const duplicateLine = (d: Draft, phaseKey: string, lineKey: string): Draft =>
  mapPhase(d, phaseKey, (p) => {
    const i = p.lines.findIndex((l) => l.key === lineKey);
    if (i < 0) return p;
    const copy: LineDraft = { ...p.lines[i], key: newKey(), alloc: { ...p.lines[i].alloc } };
    return { ...p, lines: [...p.lines.slice(0, i + 1), copy, ...p.lines.slice(i + 1)] };
  });
export const updateLine = (d: Draft, phaseKey: string, lineKey: string, patch: Partial<Omit<LineDraft, "key">>): Draft =>
  mapPhase(d, phaseKey, (p) => ({ ...p, lines: p.lines.map((l) => (l.key === lineKey ? { ...l, ...patch } : l)) }));

export const addMilestone = (d: Draft, month: string): Draft => ({ ...d, milestones: [...d.milestones, { key: newKey(), month, label: "" }] });
export const removeMilestone = (d: Draft, key: string): Draft => ({ ...d, milestones: d.milestones.filter((m) => m.key !== key) });
export const updateMilestone = (d: Draft, key: string, patch: Partial<Omit<MilestoneDraft, "key">>): Draft => ({
  ...d,
  milestones: d.milestones.map((m) => (m.key === key ? { ...m, ...patch } : m)),
});

// ---------------------------------------------------------------- incolla da Excel
/** Righe e colonne di un testo copiato da un foglio di calcolo (celle separate da tabulazioni). */
export function parseClipboard(text: string): string[][] {
  const rows = text.replace(/\r\n?/g, "\n").split("\n");
  while (rows.length && rows[rows.length - 1] === "") rows.pop();
  return rows.map((r) => r.split("\t"));
}

export const isGridPaste = (text: string): boolean => /[\t\n]/.test(text.replace(/\r?\n$/, ""));

/**
 * Incolla un blocco di celle a partire da una cella. Le righe incollate riempiono le righe successive della
 * fase (non ne crea); le colonne riempiono i mesi successivi (modalità percentuali).
 * Un valore non numerico si inserisce com'è: resta evidenziato come errore, nulla viene scartato in silenzio.
 */
export function applyPaste(d: Draft, phaseKey: string, lineKey: string, column: "hours" | string, text: string, months: string[]): Draft {
  const block = parseClipboard(text);
  const phase = d.phases.find((p) => p.key === phaseKey);
  if (!phase) return d;
  const startRow = phase.lines.findIndex((l) => l.key === lineKey);
  if (startRow < 0) return d;
  const startCol = column === "hours" ? 0 : months.indexOf(column);
  if (startCol < 0) return d;
  const clean = (cell: string): string => {
    const n = parseNumber(cell);
    return n === null ? cell.trim() : showNumber(n);
  };
  return mapPhase(d, phaseKey, (p) => ({
    ...p,
    lines: p.lines.map((line, i) => {
      const r = i - startRow;
      if (r < 0 || r >= block.length) return line;
      if (column === "hours") return { ...line, hours: clean(block[r][0] ?? "") };
      const alloc = { ...line.alloc };
      block[r].forEach((cell, c) => {
        const month = months[startCol + c];
        if (month) alloc[month] = clean(cell);
      });
      return { ...line, alloc };
    }),
  }));
}
