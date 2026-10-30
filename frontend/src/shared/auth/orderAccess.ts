export type OrderAccess = {
  actor: string;
  auth_mode: "session";
  permissions: Array<"orders:read" | "orders:write">;
  canRead: boolean;
  canWrite: boolean;
};

export function decodeOrderAccess(value: unknown): OrderAccess {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    throw new Error("Permissões de ordens inválidas.");
  }
  const row = value as Record<string, unknown>;
  if (
    typeof row.actor !== "string" ||
    !row.actor.startsWith("user:") ||
    row.auth_mode !== "session" ||
    !Array.isArray(row.permissions) ||
    !row.permissions.every(
      (permission) =>
        permission === "orders:read" || permission === "orders:write",
    )
  ) {
    throw new Error("Permissões de ordens inválidas.");
  }
  const permissions = [
    ...new Set(row.permissions),
  ] as OrderAccess["permissions"];
  return {
    actor: row.actor,
    auth_mode: "session",
    permissions,
    canRead:
      permissions.includes("orders:read") ||
      permissions.includes("orders:write"),
    canWrite: permissions.includes("orders:write"),
  };
}
