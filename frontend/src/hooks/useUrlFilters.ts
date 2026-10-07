import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { useDebounced } from "./useDebounced";

/** Filtri nell'indirizzo della pagina: si possono condividere e sopravvivono al ricaricamento. */
export function useUrlFilters() {
  const [sp, setSp] = useSearchParams();
  const get = (key: string) => sp.get(key) ?? "";
  const set = (changes: Record<string, string | null>, keepPage = false) => {
    const next = new URLSearchParams(sp);
    for (const [k, v] of Object.entries(changes)) (v ? next.set(k, v) : next.delete(k));
    if (!keepPage) next.delete("page");
    setSp(next, { replace: true });
  };
  const page = Math.max(1, Number(sp.get("page") ?? 1) || 1);
  return { get, set, page, reset: () => setSp(new URLSearchParams(), { replace: true }), active: Array.from(sp.keys()).filter((k) => k !== "page").length };
}

/** Campo di testo che aggiorna l'indirizzo dopo una breve pausa di digitazione. */
export function useTextParam(filters: ReturnType<typeof useUrlFilters>, key: string): [string, (v: string) => void] {
  const [value, setValue] = useState(filters.get(key));
  const debounced = useDebounced(value);
  useEffect(() => { if (debounced !== filters.get(key)) filters.set({ [key]: debounced || null }); }, [debounced]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { if (filters.get(key) === "" && value !== "" && debounced === "") setValue(""); }, [filters.active]); // eslint-disable-line react-hooks/exhaustive-deps
  return [value, setValue];
}
