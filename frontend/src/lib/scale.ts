/** Scale e formati per i grafici. */

/** Primo valore "tondo" (1, 2, 2,5, 5, 10 × potenza di 10) che contiene `max`. */
export function niceMax(max: number): number {
  if (!(max > 0)) return 1;
  const exp = 10 ** Math.floor(Math.log10(max));
  const f = max / exp;
  const nice = f <= 1 ? 1 : f <= 2 ? 2 : f <= 2.5 ? 2.5 : f <= 5 ? 5 : 10;
  return nice * exp;
}

/** Numeri brevi per gli assi: 1,2 M · 120 k · 850. */
export function compact(n: number): string {
  const trim = (x: number) => x.toFixed(1).replace(/\.0$/, "").replace(".", ",");
  const a = Math.abs(n);
  if (a >= 1e6) return `${trim(n / 1e6)} M`;
  if (a >= 1e3) return `${trim(n / 1e3)} k`;
  return String(Math.round(n * 10) / 10).replace(".", ",");
}

export type HeatLevel = "empty" | "low" | "high" | "over";

/** Livello di impegno di una persona in un mese (1 = 100% = una persona a tempo pieno). */
export function heatLevel(fte: number | null, overloaded: boolean): HeatLevel {
  if (overloaded) return "over";
  if (fte === null || fte <= 0) return "empty";
  return fte <= 0.5 ? "low" : "high";
}

export const HEAT_CLASS: Record<HeatLevel, string> = {
  empty: "bg-paper text-muted",
  low: "bg-teal-100 text-ink",
  high: "bg-teal text-ink",
  over: "bg-red-600 text-white font-semibold",
};
