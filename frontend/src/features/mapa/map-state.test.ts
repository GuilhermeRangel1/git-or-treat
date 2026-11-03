import { describe, expect, it } from "vitest";
import {
  buildRevenueDestination,
  parseMapSearchParams,
  type MapDefaults,
} from "./map-state";

const defaults: MapDefaults = {
  months: ["2025-01", "2025-02", "2025-03"],
  classes: ["Residencial", "Comercial"],
  municipalityCodes: ["2604106", "2611606"],
};

describe("parseMapSearchParams", () => {
  it("uses the last two published months and accepts a single-month window", () => {
    expect(parseMapSearchParams(new URLSearchParams(), defaults).query).toEqual(
      {
        competencia_inicio: "2025-02",
        competencia_fim: "2025-03",
        classe: "",
        municipio: "",
        camada: "revenue",
      },
    );
    expect(
      parseMapSearchParams(
        new URLSearchParams(
          "competencia_inicio=2025-03&competencia_fim=2025-03",
        ),
        defaults,
      ).query?.competencia_inicio,
    ).toBe("2025-03");
  });

  it.each([
    ["invalid month", "competencia_inicio=2025-13"],
    ["unpublished month", "competencia_inicio=2024-12"],
    ["reversed months", "competencia_inicio=2025-03&competencia_fim=2025-01"],
    ["repeated month", "competencia_inicio=2025-01&competencia_inicio=2025-02"],
    ["empty month", "competencia_inicio="],
    ["unknown layer", "camada=ratio"],
    ["empty layer", "camada="],
    ["unknown class", "classe=Other"],
    ["unknown municipality", "municipio=0000000"],
  ])("rejects %s without a query", (_label, query) => {
    const parsed = parseMapSearchParams(new URLSearchParams(query), defaults);
    expect(parsed.query).toBeNull();
    expect(parsed.errors).not.toHaveLength(0);
  });

  it("does not create a query before published months are available", () => {
    const parsed = parseMapSearchParams(new URLSearchParams(), {
      ...defaults,
      months: [],
    });
    expect(parsed.query).toBeNull();
  });
});

it("builds a Receita URL preserving months, class and the Gold municipality name", () => {
  expect(
    buildRevenueDestination(
      {
        competencia_inicio: "2025-01",
        competencia_fim: "2025-03",
        classe: "Comercial e Serviços",
        municipio: "2611606",
        camada: "revenue_change",
      },
      "Recife",
    ),
  ).toBe(
    "/receita?competencia_inicio=2025-01&competencia_fim=2025-03&agrupar_por=bairro&classe=Comercial+e+Servi%C3%A7os&municipio=Recife",
  );
});
