/** Token di sessione: vive solo nella scheda del browser (sessionStorage), non sopravvive alla chiusura. */
const KEY = "ce.token";

type Listener = () => void;
const listeners = new Set<Listener>();
let expired = false;

export const authStore = {
  getToken(): string | null {
    try {
      return sessionStorage.getItem(KEY);
    } catch {
      return null;
    }
  },
  setToken(token: string): void {
    expired = false;
    try {
      sessionStorage.setItem(KEY, token);
    } catch {
      /* archiviazione non disponibile: la sessione dura finché la pagina resta aperta */
    }
  },
  clear(): void {
    try {
      sessionStorage.removeItem(KEY);
    } catch {
      /* niente */
    }
  },
  /** Chiamato quando l'API risponde 401: la sessione è finita o l'utente è stato disattivato. */
  expire(): void {
    if (!authStore.getToken()) return;
    expired = true;
    authStore.clear();
    listeners.forEach((l) => l());
  },
  wasExpired(): boolean {
    return expired;
  },
  subscribe(listener: Listener): () => void {
    listeners.add(listener);
    return () => listeners.delete(listener);
  },
};
