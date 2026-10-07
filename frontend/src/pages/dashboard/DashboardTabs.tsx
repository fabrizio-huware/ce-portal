import { NavLink } from "react-router-dom";

import { ErrorBox } from "../../components/ui/Feedback";
import { useAuth } from "../../auth/AuthContext";

const tab = ({ isActive }: { isActive: boolean }) =>
  `-mb-px whitespace-nowrap border-b-2 px-4 py-2.5 text-sm font-medium ${isActive ? "border-ink text-ink" : "border-transparent text-muted hover:text-ink"}`;

export function DashboardHeader({ title, children }: { title: string; children?: React.ReactNode }) {
  return (
    <div className="mb-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-4xl font-light sm:text-5xl">Dashboard</h1>
          <p className="mt-2 text-sm text-muted">{title}</p>
        </div>
        {children}
      </div>
      <nav aria-label="Dashboard" className="mt-5 flex gap-1 overflow-x-auto border-b border-line">
        <NavLink to="/dashboard/portfolio" className={tab}>Portfolio</NavLink>
        <NavLink to="/dashboard/risorse" className={tab}>Carico risorse</NavLink>
      </nav>
    </div>
  );
}

/** Le dashboard mostrano costi e marginalità: sono riservate a admin e presale. */
export function EditorsOnly({ children }: { children: React.ReactNode }) {
  const { isEditor } = useAuth();
  return isEditor ? <>{children}</> : <ErrorBox message="Le dashboard sono riservate a chi può vedere costi e margini." />;
}
