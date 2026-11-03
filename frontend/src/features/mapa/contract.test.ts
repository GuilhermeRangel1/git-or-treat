import { describe, expect, it } from "vitest";
import type { RevenueEnvelope } from "@/shared/analytics/revenueContract";
import { municipalities } from "./municipalities";
import {
  decodeTerritoryMap,
  mapMunicipalityMetrics,
  municipalityDetailRequest,
} from "./contract";

function polygon(code: string, name: string) {
  return {
    type: "Feature",
    properties: { code, name },
    geometry: {
      type: "Polygon",
      coordinates: [
        [
          [-35, -8],
          [-34, -8],
          [-34, -7],
          [-35, -8],
        ],
      ],
    },
  };
}

function geojson() {
  return {
    type: "FeatureCollection",
    features: municipalities.map(({ code, name }) => polygon(code, name)),
  };
}

describe("decodeTerritoryMap", () => {
  it("requires every official RMR municipality with valid closed polygon rings", () => {
    const decoded = decodeTerritoryMap(geojson());
    expect(decoded.features).toHaveLength(14);
    expect(() =>
      decodeTerritoryMap({
        ...geojson(),
        features: geojson().features.slice(1),
      }),
    ).toThrow("não contém os 14");
    const malformed = geojson();
    malformed.features[0].geometry.coordinates = [
      [
        [-35, -8],
        [-34, -8],
        [Number.NaN, -7],
        [-35, -8],
      ],
    ];
    expect(() => decodeTerritoryMap(malformed)).toThrow("geometria");
  });

  it("rejects a code whose displayed official name disagrees with the registry", () => {
    const incorrect = geojson();
    incorrect.features[0].properties.name = "Outro município";
    expect(() => decodeTerritoryMap(incorrect)).toThrow("registro oficial");
  });
});

it("blocks every alias when duplicate rows map to one official municipality", () => {
  const result = mapMunicipalityMetrics({
    data: {
      breakdown: {
        dimension: "municipio",
        items: [{ label: "Olinda" }, { label: "Olinda" }, { label: "Olinda" }],
      },
    },
  } as unknown as RevenueEnvelope);
  const olinda = result.items.find(
    ({ municipality }) => municipality.name === "Olinda",
  );
  expect(olinda?.item).toBeNull();
  expect(result.unmatched).toHaveLength(3);
});

it("maps all verified uppercase Gold labels and selects Igarassu's exact detail name", () => {
  const rows = municipalities.map((municipality) => ({
    label: municipality.goldNames[0],
  }));
  const mapped = mapMunicipalityMetrics({
    data: { breakdown: { dimension: "municipio", items: rows } },
  } as unknown as RevenueEnvelope);
  expect(mapped.items.every(({ item }) => item !== null)).toBe(true);
  const igarassu = municipalities.find(({ code }) => code === "2606804")!;
  expect(
    municipalityDetailRequest(
      {
        competencia_inicio: "2025-01",
        competencia_fim: "2025-02",
        classe: "",
      },
      igarassu,
      ["IGARASSU"],
    )?.municipio,
  ).toBe("IGARASSU");
});
