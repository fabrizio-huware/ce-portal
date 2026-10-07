import { ApiError, errorMessage } from "../lib/errors";

describe("errorMessage", () => {
  it("legge i diversi formati di errore dell'API", () => {
    expect(errorMessage({ detail: "Utente non abilitato" })).toBe("Utente non abilitato");
    expect(errorMessage({ detail: [{ msg: "campo obbligatorio" }, { msg: "valore non valido" }] })).toBe("campo obbligatorio; valore non valido");
    expect(errorMessage({ detail: { message: "Non inviabile", issues: ["Manca il cliente", "Nessuna riga"] } })).toBe("Non inviabile: Manca il cliente: Nessuna riga");
    expect(errorMessage({ detail: { message: "Solo questo", issues: ["Solo questo"] } })).toBe("Solo questo");
    expect(errorMessage(new Error("Rete assente"))).toBe("Rete assente");
    expect(errorMessage("testo")).toBe("testo");
  });
  it("ha un messaggio di riserva", () => {
    for (const v of [null, undefined, {}, { detail: 5 }, 42]) expect(errorMessage(v)).toBe("Si è verificato un errore imprevisto");
  });
  it("ApiError conserva lo stato e il messaggio", () => {
    const e = new ApiError(403, { detail: "Non autorizzato" });
    expect(e.status).toBe(403);
    expect(e.message).toBe("Non autorizzato");
    expect(e).toBeInstanceOf(Error);
  });
});
