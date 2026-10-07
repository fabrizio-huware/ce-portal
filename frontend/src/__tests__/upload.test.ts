import { authStore } from "../api/authStore";
import { uploadCsv } from "../api/upload";

const res = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
const file = new File(["a;b"], "x.csv", { type: "text/csv" });
afterEach(() => vi.restoreAllMocks());
beforeEach(() => sessionStorage.clear());

describe("uploadCsv", () => {
  it("invia il file con il token e il parametro dry_run", async () => {
    authStore.setToken("tok");
    const spy = vi.spyOn(globalThis, "fetch").mockResolvedValue(res(200, { dry_run: true, applied: false, errors: [] }));
    await uploadCsv("/api/v1/employees/import", file, true);
    const [url, init] = spy.mock.calls[0];
    expect(url).toBe("/api/v1/employees/import?dry_run=true");
    expect((init!.headers as Record<string, string>).Authorization).toBe("Bearer tok");
    expect((init!.body as FormData).get("file")).toBe(file);
    await uploadCsv("/api/v1/employees/import", file, false);
    expect(spy.mock.calls[1][0]).toBe("/api/v1/employees/import?dry_run=false");
  });
  it("un 422 con gli errori di riga è un risultato, non un guasto", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(res(422, { dry_run: false, applied: false, errors: [{ line: 2, message: "x" }] }));
    const out = await uploadCsv("/x", file, false);
    expect(out.errors).toHaveLength(1);
  });
  it("gli altri errori diventano ApiError con il messaggio del server", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(res(400, { detail: "File troppo grande" }));
    await expect(uploadCsv("/x", file, true)).rejects.toMatchObject({ status: 400, message: "File troppo grande" });
  });
  it("un 401 chiude la sessione", async () => {
    authStore.setToken("tok");
    vi.spyOn(globalThis, "fetch").mockResolvedValue(res(401, { detail: "scaduta" }));
    await expect(uploadCsv("/x", file, true)).rejects.toBeTruthy();
    expect(authStore.getToken()).toBeNull();
  });
});
