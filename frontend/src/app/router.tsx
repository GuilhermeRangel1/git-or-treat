import { lazy, Suspense } from "react";
import {
  BrowserRouter,
  Navigate,
  Outlet,
  Route,
  Routes,
} from "react-router-dom";
import AppLayout from "@/layouts/AppLayout";
import { routes, UC360Page } from "./routes";

const DevContractsPage = import.meta.env.DEV
  ? lazy(() =>
      import("@/features/dev-contracts/DevContractsPage").then((module) => ({
        default: module.DevContractsPage,
      })),
    )
  : null;

export function AppRoutes() {
  return (
    <Routes>
      <Route element={<AppLayout navigation={routes} />}>
        <Route
          element={
            <Suspense fallback={<p role="status">Carregando página…</p>}>
              <Outlet />
            </Suspense>
          }
        >
          <Route index element={<Navigate to="/panorama" replace />} />
          {routes.map(({ path, Component }) => (
            <Route key={path} path={path} element={<Component />} />
          ))}
          <Route path="/uc-360/:ucId" element={<UC360Page />} />
          <Route path="*" element={<Navigate to="/panorama" replace />} />
        </Route>
      </Route>
      {DevContractsPage ? (
        <Route
          path="/dev/contratos"
          element={
            <Suspense fallback={<p role="status">Carregando diagnóstico…</p>}>
              <DevContractsPage />
            </Suspense>
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
