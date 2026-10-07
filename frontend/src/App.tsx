import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Navigate, RouterProvider, createBrowserRouter } from "react-router-dom";

import { ApiError } from "./lib/errors";
import { AuthProvider } from "./auth/AuthContext";
import { RequireAuth } from "./auth/RequireAuth";
import { AppShell } from "./layout/AppShell";
import { CeDetailPage } from "./pages/CeDetailPage";
import { CeEditPage } from "./pages/CeEditPage";
import { CeListPage } from "./pages/CeListPage";
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
