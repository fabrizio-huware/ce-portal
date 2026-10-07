import { downloadFile } from "../api/download";
import { authStore } from "../api/authStore";
import { ApiError } from "../lib/errors";

function fakeResponse(status: number, body: BodyInit | null, headers: Record<string, string> = {}) {
  return new Response(body, { status, headers });
}

beforeEach(() => {
  sessionStorage.clear();
  URL.createObjectURL = vi.fn(() => "blob:test");
  URL.revokeObjectURL = vi.fn();
});
afterEach(() => vi.restoreAllMocks());

describe("downloadFile", () => {
  it("invia il token, ignora i parametri vuoti e usa il nome del file indicato dal server", async () => {
    authStore.setToken("tok");
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(fakeResponse(200, "dati", { "Content-Disposition": 'attachment; filename="PS-X_v1.xlsx"' }));
    const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
    const name = await downloadFile("/api/v1/ce/export", { format: "xlsx", status: "", project: undefined, code: "ps x", page: 2 });
    expect(name).toBe("PS-X_v1.xlsx");
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/v1/ce/export?format=xlsx&code=ps+x&page=2");
    expect((init!.headers as Record<string, string>).Authorization).toBe("Bearer tok");
    expect(click).toHaveBeenCalledTimes(1);
  });
  it("trasforma gli errori dell'API in ApiError con il messaggio del server", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(fakeResponse(422, JSON.stringify({ detail: "Troppi risultati (6000): restringi i filtri" }), { "Content-Type": "application/json" }));
    await expect(downloadFile("/api/v1/ce/export")).rejects.toMatchObject({ status: 422, message: "Troppi risultati (6000): restringi i filtri" });
  });
  it("un 401 chiude la sessione", async () => {
    authStore.setToken("tok");
    vi.spyOn(globalThis, "fetch").mockResolvedValue(fakeResponse(401, "{}", { "Content-Type": "application/json" }));
    await expect(downloadFile("/x")).rejects.toBeInstanceOf(ApiError);
    expect(authStore.getToken()).toBeNull();
  });
  it("regge risposte di errore non JSON", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(fakeResponse(502, "<html>Bad gateway</html>"));
    await expect(downloadFile("/x")).rejects.toMatchObject({ status: 502, message: "Si è verificato un errore imprevisto" });
  });
});
