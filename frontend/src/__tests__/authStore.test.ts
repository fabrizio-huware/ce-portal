import { authStore } from "../api/authStore";

beforeEach(() => sessionStorage.clear());

describe("authStore", () => {
  it("conserva il token solo nella scheda (sessionStorage)", () => {
    expect(authStore.getToken()).toBeNull();
    authStore.setToken("abc");
    expect(authStore.getToken()).toBe("abc");
    expect(sessionStorage.getItem("ce.token")).toBe("abc");
    expect(localStorage.getItem("ce.token")).toBeNull();
    authStore.clear();
    expect(authStore.getToken()).toBeNull();
  });
  it("expire cancella il token e avvisa chi ascolta", () => {
    const listener = vi.fn();
    const off = authStore.subscribe(listener);
    authStore.setToken("abc");
    authStore.expire();
    expect(authStore.getToken()).toBeNull();
    expect(authStore.wasExpired()).toBe(true);
    expect(listener).toHaveBeenCalledTimes(1);
    off();
  });
  it("senza token expire non fa nulla (un 401 al login non è una sessione scaduta)", () => {
    const listener = vi.fn();
    const off = authStore.subscribe(listener);
    authStore.expire();
    expect(listener).not.toHaveBeenCalled();
    off();
  });
  it("un nuovo accesso azzera lo stato di scadenza", () => {
    authStore.setToken("a");
    authStore.expire();
    authStore.setToken("b");
    expect(authStore.wasExpired()).toBe(false);
  });
  it("non si rompe se lo storage non è disponibile", () => {
    const spy = vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => { throw new Error("blocked"); });
    expect(authStore.getToken()).toBeNull();
    spy.mockRestore();
  });
});
