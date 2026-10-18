import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import AppLayout from "@/layouts/AppLayout";
import { routes } from "./routes";

export function AppRoutes() {
  return (
    <Routes>
      <Route element={<AppLayout navigation={routes} />}>
        <Route index element={<Navigate to="/panorama" replace />} />
        {routes.map(({ path, Component }) => (
          <Route key={path} path={path} element={<Component />} />
        ))}
        <Route path="*" element={<Navigate to="/panorama" replace />} />
      </Route>
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
