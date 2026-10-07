import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Navigate, RouterProvider, createBrowserRouter } from "react-router-dom";

import { ApiError } from "./lib/errors";
import { AuthProvider } from "./auth/AuthContext";
import { RequireAuth } from "./auth/RequireAuth";
import { AppShell } from "./layout/AppShell";
import { CeDetailPage } from "./pages/CeDetailPage";
import { CeEditPage } from "./pages/CeEditPage";
import { CeListPage } from "./pages/CeListPage";
import { PortfolioPage } from "./pages/dashboard/PortfolioPage";
import { ResourcesPage } from "./pages/dashboard/ResourcesPage";
import { CalendarPage } from "./pages/admin/CalendarPage";
import { ClientsPage } from "./pages/admin/ClientsPage";
import { DeletedPage } from "./pages/admin/DeletedPage";
import { EmailsPage } from "./pages/admin/EmailsPage";
import { EmployeesPage } from "./pages/admin/EmployeesPage";
import { PricingPage } from "./pages/admin/PricingPage";
import { UsersPage } from "./pages/admin/UsersPage";
import { LoginPage } from "./pages/LoginPage";
import { NewCePage } from "./pages/NewCePage";
import { NotFound } from "./pages/NotFound";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 15_000,
      refetchOnWindowFocus: false,
      // Gli errori 4xx (permessi, dati non trovati) non migliorano ritentando.
      retry: (count, error) => !(error instanceof ApiError && error.status < 500) && count < 2,
    },
  },
});

const router = createBrowserRouter([
  { path: "/login", element: <LoginPage /> },
  {
    element: <RequireAuth />,
    children: [
      {
        element: <AppShell />,
        children: [
          { index: true, element: <Navigate to="/ce" replace /> },
          { path: "dashboard", element: <Navigate to="/dashboard/portfolio" replace /> },
          { path: "dashboard/portfolio", element: <PortfolioPage /> },
          { path: "dashboard/risorse", element: <ResourcesPage /> },
          { path: "admin", element: <Navigate to="/admin/utenti" replace /> },
          { path: "admin/utenti", element: <UsersPage /> },
          { path: "admin/clienti", element: <ClientsPage /> },
          { path: "admin/collaboratori", element: <EmployeesPage /> },
          { path: "admin/listino", element: <PricingPage /> },
          { path: "admin/calendario", element: <CalendarPage /> },
          { path: "admin/email", element: <EmailsPage /> },
          { path: "admin/eliminati", element: <DeletedPage /> },
          { path: "ce", element: <CeListPage /> },
          { path: "ce/nuovo", element: <NewCePage /> },
          { path: "ce/:id", element: <CeDetailPage /> },
          { path: "ce/:id/modifica", element: <CeEditPage /> },
          { path: "*", element: <NotFound /> },
        ],
      },
    ],
  },
]);

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <RouterProvider router={router} />
      </AuthProvider>
    </QueryClientProvider>
  );
}
