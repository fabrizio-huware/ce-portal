import type { ReactNode } from "react";
import { NavLink } from "react-router-dom";

import { useAuth } from "../../auth/AuthContext";
import { ErrorBox } from "../ui/Feedback";

const TABS = [
  ["/admin/utenti", "Utenti"], ["/admin/clienti", "Clienti"], ["/admin/collaboratori", "Collaboratori"], ["/admin/listino", "Listino"],
  ["/admin/calendario", "Calendario"], ["/admin/email", "Email"], ["/admin/eliminati", "CE eliminati"],
] as const;

const tab = ({ isActive }: { isActive: boolean }) =>
  `-mb-px whitespace-nowrap border-b-2 px-4 py-2.5 text-sm font-medium ${isActive ? "border-ink text-ink" : "border-transparent text-muted hover:text-ink"}`;

export function AdminHeader({ subtitle, actions }: { subtitle: string; actions?: ReactNode }) {
  return (
    <div className="mb-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-4xl font-light sm:text-5xl">Amministrazione</h1>
          <p className="mt-2 max-w-2xl text-sm text-muted">{subtitle}</p>
        </div>
        {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
      </div>
      <nav aria-label="Amministrazione" className="mt-5 flex gap-1 overflow-x-auto border-b border-line">
        {TABS.map(([to, label]) => <NavLink key={to} to={to} className={tab}>{label}</NavLink>)}
      </nav>
    </div>
  );
}

/** L'amministrazione è riservata agli admin (il server lo impone comunque: qui si evita solo una pagina inutile). */
export function AdminOnly({ children }: { children: ReactNode }) {
  const { isAdmin } = useAuth();
  return isAdmin ? <>{children}</> : <ErrorBox message="L'amministrazione è riservata agli amministratori." />;
}
