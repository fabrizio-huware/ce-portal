import { useState } from "react";
import { NavLink, Outlet } from "react-router-dom";

import { useAuth } from "../auth/AuthContext";
import { Logo } from "../components/ui/Logo";
import { ROLE_LABEL } from "../lib/status";

const navClass = ({ isActive }: { isActive: boolean }) =>
  `rounded-lg px-3 py-2 text-sm font-medium transition-colors ${isActive ? "bg-ink text-paper" : "text-ink hover:bg-surface"}`;

export function AppShell() {
  const { user, signOut, isEditor } = useAuth();
  const [open, setOpen] = useState(false);
  const links = [{ to: "/ce", label: "Conti economici" }, ...(isEditor ? [{ to: "/dashboard", label: "Dashboard" }] : [])];

  return (
    <div className="flex min-h-screen flex-col">
      <a href="#contenuto" className="sr-only focus:not-sr-only focus:absolute focus:left-3 focus:top-3 focus:z-50 focus:rounded-lg focus:bg-cyan focus:px-3 focus:py-2">Vai al contenuto</a>
      <header className="sticky top-0 z-40 border-b border-ink bg-paper">
        <div className="mx-auto flex h-16 max-w-7xl items-center gap-6 px-4 sm:px-6">
          <NavLink to="/ce" aria-label="Huware, vai all'elenco dei conti economici"><Logo className="h-6 sm:h-7" /></NavLink>
          <nav aria-label="Principale" className="hidden items-center gap-1 md:flex">
            {links.map((l) => <NavLink key={l.to} to={l.to} className={navClass}>{l.label}</NavLink>)}
          </nav>
          <div className="ml-auto hidden items-center gap-3 md:flex">
            <div className="text-right leading-tight">
              <div className="text-sm font-medium">{user?.full_name}</div>
              <div className="text-xs text-muted">{user ? ROLE_LABEL[user.role] : ""}</div>
            </div>
            <button onClick={signOut} className="rounded-lg border border-ink px-3 py-1.5 text-sm font-medium hover:bg-surface">Esci</button>
          </div>
          <button className="ml-auto grid h-10 w-10 place-items-center rounded-lg border border-line md:hidden" aria-label="Menu" aria-expanded={open} aria-controls="menu-mobile" onClick={() => setOpen((o) => !o)}>
            <svg width="20" height="20" viewBox="0 0 20 20" fill="none" aria-hidden>
              {open ? <path d="M4 4l12 12M16 4L4 16" stroke="#0a0a0a" strokeWidth="2" strokeLinecap="round" /> : <path d="M3 6h14M3 10h14M3 14h14" stroke="#0a0a0a" strokeWidth="2" strokeLinecap="round" />}
            </svg>
          </button>
        </div>
        {open && (
          <div id="menu-mobile" className="border-t border-line bg-paper px-4 pb-4 pt-2 md:hidden">
            <nav aria-label="Principale mobile" className="flex flex-col gap-1">
              {links.map((l) => <NavLink key={l.to} to={l.to} className={navClass} onClick={() => setOpen(false)}>{l.label}</NavLink>)}
            </nav>
            <div className="mt-3 flex items-center justify-between border-t border-line pt-3">
              <div className="leading-tight"><div className="text-sm font-medium">{user?.full_name}</div><div className="text-xs text-muted">{user ? ROLE_LABEL[user.role] : ""}</div></div>
              <button onClick={signOut} className="rounded-lg border border-ink px-3 py-1.5 text-sm font-medium">Esci</button>
            </div>
          </div>
        )}
      </header>
      <main id="contenuto" className="mx-auto w-full max-w-7xl flex-1 px-4 py-6 sm:px-6 sm:py-8"><Outlet /></main>
      <footer className="border-t border-line py-4 text-center text-xs text-muted">Portale Conti Economici · Huware</footer>
    </div>
  );
}
