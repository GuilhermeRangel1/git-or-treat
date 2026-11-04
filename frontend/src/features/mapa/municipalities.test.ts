import { describe, expect, it } from "vitest";

import {
  municipalities,
  municipalityByCode,
  municipalityByGoldName,
  validateMunicipalityRegistry,
} from "./municipalities";

describe("registro de municípios da RMR", () => {
  it("mantém os 14 territórios oficiais e o alias Gold observado", () => {
    expect(municipalities).toHaveLength(14);
    expect(municipalityByCode("2609402")).toMatchObject({
      name: "Moreno",
      goldNames: ["MORENO"],
    });
    expect(municipalityByGoldName("Moreno")?.code).toBe("2609402");
  });

  it("mapeia somente nomes Gold explicitamente registrados", () => {
    expect(municipalityByGoldName("Recife")?.code).toBe("2611606");
    expect(municipalityByGoldName("IGARASSU")?.code).toBe("2606804");
    expect(municipalityByGoldName("Recife ")).toBeUndefined();
    expect(municipalityByGoldName("Recif")).toBeUndefined();
  });

  it("resolve todos os aliases Gold literais observados para o código oficial", () => {
    for (const municipality of municipalities) {
      expect(municipality.goldNames.length).toBeGreaterThan(0);
      for (const goldName of municipality.goldNames) {
        expect(municipalityByGoldName(goldName)?.code).toBe(municipality.code);
      }
    }
  });

  it("rejeita códigos, nomes e aliases duplicados que criariam colisões", () => {
    const first = {
      code: "2600054",
      name: "Abreu e Lima",
      goldNames: ["Mesmo"],
    } as const;
    expect(() => validateMunicipalityRegistry([first, first])).toThrow(
      /Código IBGE duplicado/,
    );
    expect(() =>
      validateMunicipalityRegistry([
        first,
        { code: "2601052", name: "Araçoiaba", goldNames: ["Mesmo"] },
      ]),
    ).toThrow(/Nome municipal ambíguo/);
    expect(() =>
      validateMunicipalityRegistry([
        { code: "2600054", name: "Abreu e Lima", goldNames: ["Araçoiaba"] },
        { code: "2601052", name: "Araçoiaba", goldNames: [] },
      ]),
    ).toThrow(/Nome municipal ambíguo/);
  });

  it("rejeita nomes oficiais ausentes e códigos IBGE inválidos", () => {
    expect(() =>
      validateMunicipalityRegistry([
        { code: "2600054", name: "   ", goldNames: [] },
      ]),
    ).toThrow(/Nome oficial ausente/);
    expect(() =>
      validateMunicipalityRegistry([
        { code: "260054", name: "Abreu e Lima", goldNames: [] },
      ]),
    ).toThrow(/Código IBGE inválido/);
  });
});
