import { describe, expect, it } from "vitest";
import { decodeOrderAccess } from "./orderAccess";

describe("permissões de ordens", () => {
  it("aceita somente permissões concedidas pela API", () => {
    expect(
      decodeOrderAccess({
        actor: "oidc:opaque-id",
        auth_mode: "oidc",
        permissions: ["orders:read"],
      }).canWrite,
    ).toBe(false);
  });

  it("rejeita resposta de acesso fora do contrato", () => {
    expect(() =>
      decodeOrderAccess({
        actor: "oidc:opaque-id",
        auth_mode: "oidc",
        permissions: ["orders:admin"],
      }),
    ).toThrow("Permissões de ordens inválidas.");
  });
});
