import { describe, expect, it } from "vitest";
import { decodeOrderAccess } from "./orderAccess";

describe("permissões de ordens", () => {
  it("aceita somente permissões concedidas pela API", () => {
    expect(
      decodeOrderAccess({
        actor: "user:opaque-id",
        auth_mode: "session",
        permissions: ["orders:read"],
      }).canWrite,
    ).toBe(false);
  });

  it("rejeita resposta de acesso fora do contrato", () => {
    expect(() =>
      decodeOrderAccess({
        actor: "user:opaque-id",
        auth_mode: "session",
        permissions: ["orders:admin"],
      }),
    ).toThrow("Permissões de ordens inválidas.");
  });
});
