import { lazy, Suspense } from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import AppLayout from "@/layouts/AppLayout";
import UC360Page from "@/features/uc360/UC360Page";
import { routes } from "./routes";

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
        <Route index element={<Navigate to="/panorama" replace />} />
        {routes.map(({ path, Component }) => (
          <Route key={path} path={path} element={<Component />} />
        ))}
        <Route path="/uc-360/:ucId" element={<UC360Page />} />
        <Route path="*" element={<Navigate to="/panorama" replace />} />
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
