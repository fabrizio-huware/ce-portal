import { Link } from "react-router-dom";

export function NotFound() {
  return (
    <div className="grid place-items-center py-24 text-center">
      <p className="text-sm font-medium uppercase tracking-wide text-muted">Errore 404</p>
      <h1 className="mt-2 text-4xl font-light">Pagina non trovata</h1>
      <Link to="/ce" className="mt-6 rounded-lg bg-cyan px-4 py-2.5 text-sm font-medium hover:bg-cyan-300">Torna ai conti economici</Link>
    </div>
  );
}
