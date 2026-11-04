export const PLATFORM_PERMISSIONS = [
  "panorama:read",
  "revenue:read",
  "ucs:read",
  "inspections:read",
  "orders:read",
  "orders:write",
  "operations:read",
  "ai:ask",
] as const;

export type PlatformPermission = (typeof PLATFORM_PERMISSIONS)[number];
export type PlatformProfile =
  "commercial" | "customer_service" | "losses" | "operations" | "admin";
export type PlatformIdentity = {
  profile: PlatformProfile | null;
  permissions: PlatformPermission[];
};

export const PROFILE_PERMISSIONS: Record<
  PlatformProfile,
  readonly PlatformPermission[]
> = {
  commercial: ["panorama:read", "revenue:read", "ai:ask"],
  customer_service: ["ucs:read", "ai:ask"],
  losses: ["inspections:read", "orders:read", "orders:write", "ai:ask"],
  operations: ["operations:read", "ai:ask"],
  admin: PLATFORM_PERMISSIONS,
};

const DEFAULT_ROUTES: Record<PlatformProfile, string> = {
  commercial: "/panorama",
  customer_service: "/uc-360",
  losses: "/inspecoes",
  operations: "/operacao",
  admin: "/panorama",
};

export function hasPermission(
  user: PlatformIdentity | null,
  permission: PlatformPermission,
): boolean {
  if (!user?.profile) return false;
  return (
    PROFILE_PERMISSIONS[user.profile].includes(permission) &&
    user.permissions.includes(permission)
  );
}

export function getDefaultRoute(user: PlatformIdentity | null): string | null {
  if (!user?.profile) return null;
  const route = DEFAULT_ROUTES[user.profile];
  const permission = {
    "/panorama": "panorama:read",
    "/uc-360": "ucs:read",
    "/inspecoes": "inspections:read",
    "/operacao": "operations:read",
  }[route] as PlatformPermission | undefined;
  return permission && hasPermission(user, permission) ? route : null;
}
