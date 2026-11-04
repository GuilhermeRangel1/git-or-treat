import type { ReactNode } from "react";
import { Navigate } from "react-router-dom";
import { useSession } from "./useSession";
import AccessDenied from "./AccessDenied";
import { hasPermission, type PlatformPermission } from "./platformAccess";

export default function RequirePermission({
  children,
  permission,
  adminOnly = false,
}: {
  children: ReactNode;
  permission?: PlatformPermission;
  adminOnly?: boolean;
}) {
  const { configured, user } = useSession();
  if (!configured) return children;
  if (!user) return <Navigate to="/login" replace />;
  const allowed = adminOnly
    ? user.profile === "admin"
    : permission !== undefined && hasPermission(user, permission);
  return allowed ? children : <AccessDenied />;
}
