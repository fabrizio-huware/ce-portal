/** Numeri scritti dall'utente: si accettano la virgola e il punto, anche nel formato italiano (1.234,5). */

/**
 * Normalizza un numero scritto a mano in "1234.5". Restituisce `null` se non è un numero valido.
 * - "12,5" e "12.5" valgono 12,5;
 * - con la virgola, i punti sono separatori delle migliaia ("1.234,5" = 1234,5);
 * - un punto seguito da esattamente tre cifre ("1.234", "12.345.678") è un separatore delle migliaia;
 * - il segno "%" finale (incollato da Excel) viene ignorato.
 */
export function parseNumber(text: string): string | null {
  let t = text.trim().replace(/\s+/g, "").replace(/%$/, "");
  if (t === "") return "";
  if (!/^[0-9.,]+$/.test(t)) return null;
  if (t.includes(",")) {
    if (t.indexOf(",") !== t.lastIndexOf(",")) return null;
    t = t.replace(/\./g, "").replace(",", ".");
  } else if (/^\d{1,3}(\.\d{3})+$/.test(t)) {
    t = t.replace(/\./g, "");
  } else if ((t.match(/\./g) ?? []).length > 1) {
    return null;
  }
  if (!/^\d+(\.\d*)?$|^\.\d+$/.test(t)) return null;
  return t.startsWith(".") ? "0" + t : t.endsWith(".") ? t.slice(0, -1) : t;
}

export type NumberRule = { max?: number; decimals?: number; integer?: boolean };

/** Messaggio di errore per un campo numerico (stringa vuota = nessun errore: il campo è facoltativo o ha un valore automatico). */
export function numberError(text: string, rule: NumberRule = {}): string | null {
  const n = parseNumber(text);
  if (n === null) return "Inserisci un numero";
  if (n === "") return null;
  const decimals = rule.integer ? 0 : (rule.decimals ?? 2);
  const [, dec = ""] = n.split(".");
  if (dec.length > decimals) return decimals === 0 ? "Solo numeri interi" : `Al massimo ${decimals} decimali`;
  if (rule.max !== undefined && Number(n) > rule.max) return `Al massimo ${rule.max}`;
  return null;
}

/** Valore da mostrare: il punto decimale diventa virgola. */
export function showNumber(value: string | null | undefined): string {
  if (value === null || value === undefined) return "";
  return value.replace(".", ",");
}
