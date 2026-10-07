import { Navigate, Outlet, useLocation } from "react-router-dom";

import { Spinner } from "../components/ui/Spinner";
import { useAuth } from "./AuthContext";

export function RequireAuth() {
  const { state } = useAuth();
  const location = useLocation();
  if (state.status === "loading") return <div className="grid min-h-screen place-items-center"><Spinner label="Verifica dell'accesso…" /></div>;
  if (state.status === "anon") return <Navigate to="/login" replace state={{ from: location.pathname + location.search }} />;
  return <Outlet />;
}
