/** Formati italiani, indipendenti dalle impostazioni internazionali del browser. */

function group(integer: string): string {
  return integer.replace(/\B(?=(\d{3})+(?!\d))/g, ".");
}

export function num(value: string | number | null | undefined, digits = 2): string {
  if (value === null || value === undefined || value === "") return "—";
  const n = Number(value);
  if (!Number.isFinite(n)) return "—";
  const fixed = Math.abs(n).toFixed(digits);
  const [int, dec] = fixed.split(".");
  const sign = n < 0 && Number(fixed) !== 0 ? "-" : "";
  return sign + group(int) + (dec ? "," + dec : "");
}

export function money(value: string | number | null | undefined): string {
  const text = num(value, 2);
  return text === "—" ? text : `${text} €`;
}

/** Frazione (0.5717) -> percentuale ("57,17%"). `null` = non calcolabile. */
export function pct(fraction: string | number | null | undefined, digits = 2): string {
  if (fraction === null || fraction === undefined) return "n/d";
  return `${num(Number(fraction) * 100, digits)}%`;
}

/** Percentuale già espressa in punti (10 -> "10,00%"). */
export function points(value: string | number | null | undefined): string {
  return value === null || value === undefined ? "—" : `${num(value, 2)}%`;
}

export function date(iso: string | null | undefined): string {
  if (!iso) return "—";
  const [y, m, d] = iso.slice(0, 10).split("-");
  return `${d}/${m}/${y}`;
}

const MONTHS = ["gen", "feb", "mar", "apr", "mag", "giu", "lug", "ago", "set", "ott", "nov", "dic"];
export function month(iso: string): string {
  const [y, m] = iso.split("-");
  return `${MONTHS[Number(m) - 1]} ${y}`;
}

export function datetime(iso: string | null | undefined): string {
  if (!iso) return "—";
  const parts = new Intl.DateTimeFormat("it-IT", {
    timeZone: "Europe/Rome", day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit",
  }).formatToParts(new Date(iso));
  const get = (t: string) => parts.find((p) => p.type === t)?.value ?? "";
  return `${get("day")}/${get("month")}/${get("year")} ${get("hour")}:${get("minute")}`;
}

export function period(start: string, end: string): string {
  return `${date(start)} – ${date(end)}`;
}
