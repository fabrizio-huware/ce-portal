import { useCallback, useState, type FormEvent } from "react";
import { Navigate, useLocation } from "react-router-dom";

import { api, unwrap } from "../api/client";
import { authStore } from "../api/authStore";
import { useAuth } from "../auth/AuthContext";
import { GoogleButton } from "../auth/GoogleButton";
import { Button } from "../components/ui/Button";
import { ErrorBox, Notice } from "../components/ui/Feedback";
import { Logo } from "../components/ui/Logo";
import { errorMessage } from "../lib/errors";

export function LoginPage() {
  const GOOGLE_CLIENT_ID: string = import.meta.env.VITE_GOOGLE_CLIENT_ID ?? "";
  const DEV_LOGIN = import.meta.env.VITE_ENABLE_DEV_LOGIN === "true";
  const { state, signIn } = useAuth();
  const location = useLocation();
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [email, setEmail] = useState("");
  const from = (location.state as { from?: string } | null)?.from ?? "/ce";

  const loginWithGoogle = useCallback(async (idToken: string) => {
    setError(null);
    setBusy(true);
    try {
      const out = unwrap(await api.POST("/api/v1/auth/google", { body: { id_token: idToken } }));
      signIn(out.access_token, out.user);
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }, [signIn]);

  async function loginDev(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const out = unwrap(await api.POST("/api/v1/auth/dev-login", { body: { email } }));
      signIn(out.access_token, out.user);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  if (state.status === "authed") return <Navigate to={from} replace />;
  const expired = state.status === "anon" && (state.expired || authStore.wasExpired());

  return (
    <div className="grid min-h-screen lg:grid-cols-[1.1fr_1fr]">
      <section className="relative hidden flex-col justify-between overflow-hidden bg-ink p-12 text-paper lg:flex">
        <Logo variant="white" className="h-8" />
        <div>
          <h1 className="text-6xl font-light leading-[1.2] tracking-tightest">
            Conti economici<br />di progetto, <span className="hl">chiari</span><br />e <span className="hl">condivisi</span>.
          </h1>
          <p className="mt-6 max-w-md text-lg text-paper/70">Costi, marginalità e impegno delle risorse per ogni progetto, in un unico posto.</p>
        </div>
        <div className="h-1 w-24 rounded-full bg-teal" aria-hidden />
      </section>
      <section className="flex flex-col justify-center px-6 py-12 sm:px-12">
        <div className="mx-auto w-full max-w-sm">
          <div className="mb-10 lg:hidden"><Logo className="h-7" /></div>
          <h2 className="text-3xl font-light tracking-tightest">Accedi</h2>
          <p className="mt-2 text-sm text-muted">Usa il tuo account Google aziendale. L'accesso è riservato agli utenti abilitati da un amministratore.</p>
          <div className="mt-8 space-y-4">
            {expired && <Notice>La sessione è scaduta. Accedi di nuovo per continuare.</Notice>}
            {error && <ErrorBox message={error} />}
            {GOOGLE_CLIENT_ID ? (
              <GoogleButton clientId={GOOGLE_CLIENT_ID} onCredential={loginWithGoogle} />
            ) : !DEV_LOGIN ? (
              <ErrorBox message="L'accesso con Google non è ancora configurato. Contatta un amministratore." />
            ) : null}
            {DEV_LOGIN && (
              <form onSubmit={loginDev} className="rounded-xl border border-dashed border-ink/40 p-4" aria-label="Accesso di sviluppo">
                <p className="mb-3 text-xs font-medium uppercase tracking-wide text-muted">Solo sviluppo locale</p>
                <label htmlFor="dev-email" className="label">Email di un utente registrato</label>
                <input id="dev-email" type="email" required autoComplete="username" className="field" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="nome.cognome@huware.com" />
                <Button type="submit" variant="accent" className="mt-3 w-full" loading={busy}>Entra senza Google</Button>
              </form>
            )}
          </div>
        </div>
      </section>
    </div>
  );
}
