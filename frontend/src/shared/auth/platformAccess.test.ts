import { describe, expect, it } from "vitest";
import {
  getDefaultRoute,
  hasPermission,
  type PlatformProfile,
} from "./platformAccess";

const permissions = [
  "panorama:read",
  "revenue:read",
  "ucs:read",
  "inspections:read",
  "orders:read",
  "orders:write",
  "operations:read",
  "ai:ask",
] as const;

const profilePermissions: Record<PlatformProfile, readonly string[]> = {
  commercial: ["panorama:read", "revenue:read", "ai:ask"],
  customer_service: ["ucs:read", "ai:ask"],
  losses: ["inspections:read", "orders:read", "orders:write", "ai:ask"],
  operations: ["operations:read", "ai:ask"],
  admin: permissions,
};

describe("acesso às áreas da plataforma", () => {
  it.each(Object.entries(profilePermissions))(
    "aplica permissões de %s às jornadas autorizadas",
    (profile, allowed) => {
      const user = {
        profile: profile as PlatformProfile,
        permissions: [...allowed] as (typeof permissions)[number][],
      };
      for (const permission of permissions) {
        expect(hasPermission(user, permission)).toBe(
          allowed.includes(permission),
        );
      }
    },
  );

  it("não libera acesso a um perfil sem provisão mesmo com permissões no objeto", () => {
    expect(
      hasPermission(
        { profile: null, permissions: ["panorama:read"] },
        "panorama:read",
      ),
    ).toBe(false);
  });

  it.each([
    ["commercial", "/panorama"],
    ["customer_service", "/uc-360"],
    ["losses", "/inspecoes"],
    ["operations", "/operacao"],
    ["admin", "/panorama"],
  ] as const)("abre %s na rota %s", (profile, expected) => {
    expect(
      getDefaultRoute({
        profile,
        permissions: [
          ...profilePermissions[profile],
        ] as (typeof permissions)[number][],
      }),
    ).toBe(expected);
  });

  it("não escolhe destino para perfil sem rota autorizada", () => {
    expect(getDefaultRoute({ profile: null, permissions: [] })).toBeNull();
  });
});
