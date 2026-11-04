import { lazy, Suspense } from "react";
import {
  BrowserRouter,
  Navigate,
  Outlet,
  Route,
  Routes,
} from "react-router-dom";
import AppLayout from "@/layouts/AppLayout";
import RequireSession from "@/shared/auth/RequireSession";
import RequirePermission from "@/shared/auth/RequirePermission";
import AccessDenied from "@/shared/auth/AccessDenied";
import { getDefaultRoute } from "@/shared/auth/platformAccess";
import { useSession } from "@/shared/auth/useSession";
import LoginPage from "@/features/auth/LoginPage";
import { routes, UC360Page } from "./routes";

const DevContractsPage = import.meta.env.DEV
  ? lazy(() =>
      import("@/features/dev-contracts/DevContractsPage").then((module) => ({
        default: module.DevContractsPage,
      })),
    )
  : null;

function DefaultRoute() {
  const { configured, user } = useSession();
  const destination = configured ? getDefaultRoute(user) : "/panorama";
  return destination ? <Navigate to={destination} replace /> : <AccessDenied />;
}

export function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        element={
          <RequireSession>
            <AppLayout navigation={routes} />
          </RequireSession>
        }
      >
        <Route
          element={
            <Suspense fallback={<p role="status">Carregando página…</p>}>
              <Outlet />
            </Suspense>
          }
        >
          <Route index element={<DefaultRoute />} />
          {routes.map(({ path, Component, requiredPermission }) => (
            <Route
              key={path}
              path={path}
              element={
                <RequirePermission permission={requiredPermission}>
                  <Component />
                </RequirePermission>
              }
            />
          ))}
          <Route
            path="/uc-360/:ucId"
            element={
              <RequirePermission permission="ucs:read">
                <UC360Page />
              </RequirePermission>
            }
          />
          <Route path="*" element={<DefaultRoute />} />
        </Route>
      </Route>
      {DevContractsPage ? (
        <Route
          path="/dev/contratos"
          element={
            <RequireSession>
              <Suspense fallback={<p role="status">Carregando diagnóstico…</p>}>
                <RequirePermission adminOnly>
                  <DevContractsPage />
                </RequirePermission>
              </Suspense>
            </RequireSession>
          }
        />
      ) : null}
    </Routes>
  );
}

export default function AppRouter() {
  return (
    <BrowserRouter>
      <AppRoutes />
    </BrowserRouter>
  );
}
