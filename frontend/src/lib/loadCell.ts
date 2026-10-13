import { num } from "./format";

/** Cosa mostrare in ogni cella del carico risorse: percentuale, giorni, ore, oppure percentuale e giorni insieme (predefinito). */
export type CellMode = "both" | "pct" | "days" | "hours";

export const CELL_MODES: { value: CellMode; label: string }[] = [
  { value: "pct", label: "Percentuale" },
  { value: "days", label: "Giorni" },
  { value: "hours", label: "Ore" },
  { value: "both", label: "Entrambi" },
];

/** Nell'indirizzo il valore predefinito (entrambi) non si scrive: `?celle=pct`, `?celle=giorni` o `?celle=ore`. */
export function parseCellMode(param: string | null | undefined): CellMode {
  return param === "pct" ? "pct" : param === "giorni" ? "days" : param === "ore" ? "hours" : "both";
}

export function cellModeParam(mode: CellMode): string | null {
  return mode === "pct" ? "pct" : mode === "days" ? "giorni" : mode === "hours" ? "ore" : null;
}

export type LoadCell = { fte: string | number | null | undefined; days: string | number; hours: string | number; overloaded: boolean };
export type CellView = { primary: string; secondary: string | null; empty: boolean };

/**
 * Arrotonda «da 5 in su» lavorando sulle cifre decimali scritte, non sul numero binario: in binario 19,95 vale
 * 19,9499… e `toFixed(1)` darebbe «19,9», mentre il server ed Excel danno «20,0».
 */
export function roundHalfUp(value: string | number, digits: number): string {
  const text = typeof value === "number" ? value.toFixed(10) : value.trim();
  const m = /^(-?)(\d+)(?:\.(\d+))?$/.exec(text);
  if (!m) return num(Number(value), digits);
  const [, sign, int, frac = ""] = m;
  const padded = frac.padEnd(digits + 1, "0");
  const kept = (int + padded.slice(0, digits)).split("");
  if (padded.charCodeAt(digits) >= 53) {
    // la cifra successiva è 5 o più: si aggiunge una unità all'ultima cifra tenuta, riportando
    let i = kept.length - 1;
    while (i >= 0) {
      if (kept[i] === "9") { kept[i] = "0"; i--; } else { kept[i] = String(Number(kept[i]) + 1); break; }
    }
    if (i < 0) kept.unshift("1");
  }
  const digitsOnly = kept.join("");
  const intPart = digits ? digitsOnly.slice(0, digitsOnly.length - digits) : digitsOnly;
  const decimal = digits ? `${intPart}.${digitsOnly.slice(digitsOnly.length - digits)}` : intPart;
  return num(`${sign}${decimal}`, digits);
}

/** Giorni o ore con un decimale; un impegno minuscolo ma reale non si arrotonda a «0,0». */
function oneDecimal(value: string | number): string {
  const n = Number(value);
  return n > 0 && n < 0.05 ? "<0,1" : roundHalfUp(value, 1);
}

export const daysText = (days: string | number): string => oneDecimal(days);
/** Le ore le calcola il server (giorni × 8): qui si formattano soltanto. */
export const hoursText = (hours: string | number): string => oneDecimal(hours);

/**
 * Testo della cella. Il sovraccarico è segnalato da ⚠ (e dal colore): mai solo dal colore.
 * - «both»: percentuale in evidenza e sotto i giorni in piccolo («10,8 gg»);
 * - «pct»: solo la percentuale; «days» e «hours»: solo i giorni o solo le ore (senza unità: la dice il pulsante scelto e il
 *   suggerimento). Il colore e il ⚠ restano sempre legati alla percentuale.
 */
export function formatLoadCell(mode: CellMode, cell: LoadCell): CellView {
  if (cell.fte === null || cell.fte === undefined || Number(cell.days) === 0) return { primary: "—", secondary: null, empty: true };
  const warn = cell.overloaded ? "⚠ " : "";
  const pct = `${Math.round(Number(cell.fte) * 100)}%`;
  const days = daysText(cell.days);
  if (mode === "pct") return { primary: `${warn}${pct}`, secondary: null, empty: false };
  if (mode === "days") return { primary: `${warn}${days}`, secondary: null, empty: false };
  if (mode === "hours") return { primary: `${warn}${hoursText(cell.hours)}`, secondary: null, empty: false };
  return { primary: `${warn}${pct}`, secondary: `${days} gg`, empty: false };
}
