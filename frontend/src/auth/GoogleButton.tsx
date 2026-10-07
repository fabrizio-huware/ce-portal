import { useEffect, useRef, useState } from "react";

type Props = { clientId: string; onCredential: (idToken: string) => void };

type GoogleId = {
  initialize: (config: { client_id: string; callback: (r: { credential: string }) => void }) => void;
  renderButton: (el: HTMLElement, options: Record<string, unknown>) => void;
};
declare global {
  interface Window {
    google?: { accounts: { id: GoogleId } };
  }
}

const SCRIPT = "https://accounts.google.com/gsi/client";

/** Pulsante "Accedi con Google" (Google Identity Services). Restituisce l'ID token da inviare al backend. */
export function GoogleButton({ clientId, onCredential }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const init = () => {
      if (cancelled || !ref.current || !window.google) return;
      window.google.accounts.id.initialize({ client_id: clientId, callback: (r) => onCredential(r.credential) });
      window.google.accounts.id.renderButton(ref.current, {
        theme: "filled_black", size: "large", shape: "rectangular", text: "signin_with", locale: "it", width: 300,
      });
    };
    if (window.google) {
      init();
    } else {
      const existing = document.querySelector<HTMLScriptElement>(`script[src="${SCRIPT}"]`);
      const script = existing ?? Object.assign(document.createElement("script"), { src: SCRIPT, async: true });
      script.addEventListener("load", init);
      script.addEventListener("error", () => setFailed(true));
      if (!existing) document.head.appendChild(script);
    }
    return () => {
      cancelled = true;
    };
  }, [clientId, onCredential]);

  if (failed) return <p role="alert" className="text-sm text-red-700">Impossibile caricare l'accesso con Google. Controlla la connessione.</p>;
  return <div ref={ref} className="min-h-[44px]" aria-label="Accedi con Google" />;
}
