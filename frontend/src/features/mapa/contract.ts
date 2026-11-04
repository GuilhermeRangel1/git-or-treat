import {
  municipalityByGoldName,
  municipalityByCode,
  municipalities,
  type TerritoryMunicipality,
} from "./municipalities";
import type { RevenueEnvelope } from "@/shared/analytics/revenueContract";
import {
  fetchRevenueForContext,
  type RevenueRequest,
} from "@/shared/analytics/revenueClient";

export type TerritoryMapFeature = {
  type: "Feature";
  properties: { code: string; name: string };
  geometry: {
    type: "Polygon" | "MultiPolygon";
    coordinates: unknown[];
  };
};

export type TerritoryMapGeoJSON = {
  type: "FeatureCollection";
  features: TerritoryMapFeature[];
};

export type MunicipalityMetric = {
  municipality: TerritoryMunicipality;
  item: RevenueEnvelope["data"]["breakdown"]["items"][number] | null;
};

function object(value: unknown, label: string): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value))
    throw new Error(`${label} inválido.`);
  return value as Record<string, unknown>;
}

export function decodeTerritoryMap(value: unknown): TerritoryMapGeoJSON {
  const root = object(value, "GeoJSON");
  if (root.type !== "FeatureCollection" || !Array.isArray(root.features))
    throw new Error("A malha da RMR não contém FeatureCollection.");
  const features = root.features.map((input, index) => {
    const feature = object(input, `features[${index}]`);
    const properties = object(
      feature.properties,
      `features[${index}].properties`,
    );
    const geometry = object(feature.geometry, `features[${index}].geometry`);
    if (
      feature.type !== "Feature" ||
      typeof properties.code !== "string" ||
      typeof properties.name !== "string" ||
      (geometry.type !== "Polygon" && geometry.type !== "MultiPolygon") ||
      !Array.isArray(geometry.coordinates)
    ) {
      throw new Error(
        `features[${index}] não corresponde ao contrato territorial.`,
      );
    }
    const coordinates = geometry.coordinates;
    const isPosition = (position: unknown): position is number[] =>
      Array.isArray(position) &&
      position.length >= 2 &&
      typeof position[0] === "number" &&
      Number.isFinite(position[0]) &&
      position[0] >= -180 &&
      position[0] <= 180 &&
      typeof position[1] === "number" &&
      Number.isFinite(position[1]) &&
      position[1] >= -90 &&
      position[1] <= 90;
    const isRing = (ring: unknown) =>
      Array.isArray(ring) &&
      ring.length >= 4 &&
      ring.every(isPosition) &&
      ring[0][0] === ring[ring.length - 1][0] &&
      ring[0][1] === ring[ring.length - 1][1];
    const validCoordinates =
      geometry.type === "Polygon"
        ? coordinates.length > 0 && coordinates.every(isRing)
        : coordinates.length > 0 &&
          coordinates.every(
            (polygon) =>
              Array.isArray(polygon) &&
              polygon.length > 0 &&
              polygon.every(isRing),
          );
    const municipality = municipalityByCode(properties.code);
    if (
      !validCoordinates ||
      !municipality ||
      municipality.name !== properties.name
    ) {
      throw new Error(
        `features[${index}] tem geometria ou identificação fora do registro oficial.`,
      );
    }
    return {
      type: "Feature" as const,
      properties: { code: properties.code, name: properties.name },
      geometry: {
        type: geometry.type as "Polygon" | "MultiPolygon",
        coordinates,
      },
    };
  });
  const allowed = new Set(
    municipalities.map((municipality) => municipality.code),
  );
  const codes = new Set<string>();
  for (const feature of features) {
    if (
      !allowed.has(feature.properties.code) ||
      codes.has(feature.properties.code)
    )
      throw new Error(
        `Código territorial desconhecido ou duplicado: ${feature.properties.code}.`,
      );
    codes.add(feature.properties.code);
  }
  if (codes.size !== allowed.size) {
    throw new Error(
      "A malha local não contém os 14 municípios oficiais da RMR.",
    );
  }
  return { type: "FeatureCollection", features };
}

export function mapMunicipalityMetrics(envelope: RevenueEnvelope) {
  if (envelope.data.breakdown.dimension !== "municipio")
    throw new Error(
      "A resposta da visão regional não está agrupada por município.",
    );
  const matched = new Map<
    string,
    RevenueEnvelope["data"]["breakdown"]["items"][number]
  >();
  const ambiguous = new Set<string>();
  const unmatched: string[] = [];
  for (const item of envelope.data.breakdown.items) {
    const municipality = municipalityByGoldName(item.label);
    if (!municipality) {
      unmatched.push(item.label);
      continue;
    }
    if (ambiguous.has(municipality.code)) {
      unmatched.push(item.label);
      continue;
    }
    if (matched.has(municipality.code)) {
      const previous = matched.get(municipality.code);
      if (previous) unmatched.push(previous.label);
      matched.delete(municipality.code);
      ambiguous.add(municipality.code);
      unmatched.push(item.label);
      continue;
    }
    matched.set(municipality.code, item);
  }
  return {
    items: municipalities.map((municipality) => ({
      municipality,
      item: matched.get(municipality.code) ?? null,
    })),
    unmatched,
  };
}

export function municipalityDetailRequest(
  request: Omit<RevenueRequest, "municipio" | "group_by" | "bairro">,
  municipality: TerritoryMunicipality,
  catalogMunicipalities: readonly string[],
): RevenueRequest | null {
  const name = [municipality.name, ...municipality.goldNames].find(
    (candidate) => catalogMunicipalities.includes(candidate),
  );
  if (!name) return null;
  return {
    ...request,
    municipio: name,
    bairro: "",
    group_by: "bairro",
  };
}

export function validateMunicipalityDetail(
  envelope: RevenueEnvelope,
  request: RevenueRequest,
) {
  if (
    envelope.metadata.filters.municipio !== request.municipio ||
    envelope.data.breakdown.dimension !== "bairro"
  ) {
    throw new Error(
      "A resposta detalhada não corresponde ao município selecionado.",
    );
  }
  return envelope;
}

export { fetchRevenueForContext };
