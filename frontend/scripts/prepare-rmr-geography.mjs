import { createHash } from "node:crypto";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const scriptDirectory = path.dirname(fileURLToPath(import.meta.url));
const frontendDirectory = path.resolve(scriptDirectory, "..");
const outputDirectory = path.join(frontendDirectory, "public", "geography");
const geoJsonPath = path.join(outputDirectory, "rmr.geojson");
const metadataPath = path.join(outputDirectory, "rmr-metadata.json");
const BASE_URL = "https://servicodados.ibge.gov.br/api/v3/malhas/municipios";
const PERIOD = "2022";

// Espelho da composição documentada em municipalities.ts; os códigos strings
// preservam zeros à esquerda quando houver e são o identificador de união.
export const officialMunicipalities = [
  { code: "2600054", name: "Abreu e Lima" },
  { code: "2601052", name: "Araçoiaba" },
  { code: "2602902", name: "Cabo de Santo Agostinho" },
  { code: "2603454", name: "Camaragibe" },
  { code: "2606804", name: "Igarassu" },
  { code: "2607604", name: "Ilha de Itamaracá" },
  { code: "2607208", name: "Ipojuca" },
  { code: "2607752", name: "Itapissuma" },
  { code: "2607901", name: "Jaboatão dos Guararapes" },
  { code: "2609402", name: "Moreno" },
  { code: "2609600", name: "Olinda" },
  { code: "2610707", name: "Paulista" },
  { code: "2611606", name: "Recife" },
  { code: "2613701", name: "São Lourenço da Mata" },
];

function hash(bytes) {
  return createHash("sha256").update(bytes).digest("hex");
}

function coordinatesAreValid(coordinates) {
  if (!Array.isArray(coordinates) || coordinates.length === 0) return false;
  if (typeof coordinates[0] === "number") {
    return (
      coordinates.length >= 2 &&
      coordinates.every(Number.isFinite) &&
      coordinates[0] >= -180 &&
      coordinates[0] <= 180 &&
      coordinates[1] >= -90 &&
      coordinates[1] <= 90
    );
  }
  return coordinates.every(coordinatesAreValid);
}

function ringsAreClosed(coordinates, geometryType) {
  const polygons = geometryType === "Polygon" ? [coordinates] : coordinates;
  return polygons.every((polygon) =>
    polygon.every((ring) => {
      if (!Array.isArray(ring) || ring.length < 4) return false;
      const first = ring[0];
      const last = ring[ring.length - 1];
      return first[0] === last[0] && first[1] === last[1];
    }),
  );
}

export function buildRmrFeatureCollection(
  sourceCollections,
  municipalities = officialMunicipalities,
) {
  const expected = new Map(
    municipalities.map((municipality) => [municipality.code, municipality]),
  );
  if (expected.size !== municipalities.length)
    throw new Error("Código municipal duplicado no registro.");

  const features = [];
  const found = new Set();
  for (const collection of sourceCollections) {
    if (
      collection?.type !== "FeatureCollection" ||
      !Array.isArray(collection.features)
    ) {
      throw new Error("Resposta do IBGE não é uma FeatureCollection válida.");
    }
    for (const feature of collection.features) {
      const code = String(
        feature?.properties?.codarea ?? feature?.properties?.code ?? "",
      );
      const municipality = expected.get(code);
      if (!municipality)
        throw new Error(`Código IBGE inesperado: ${code || "ausente"}.`);
      if (found.has(code)) throw new Error(`Geometria duplicada para ${code}.`);
      const geometry = feature.geometry;
      if (!geometry || !["Polygon", "MultiPolygon"].includes(geometry.type)) {
        throw new Error(`Geometria inválida para ${code}.`);
      }
      if (
        !coordinatesAreValid(geometry.coordinates) ||
        !ringsAreClosed(geometry.coordinates, geometry.type)
      ) {
        throw new Error(`Coordenadas ou anéis inválidos para ${code}.`);
      }
      found.add(code);
      features.push({
        type: "Feature",
        properties: { code, name: municipality.name },
        geometry,
      });
    }
  }

  const missing = [...expected.keys()].filter((code) => !found.has(code));
  if (missing.length)
    throw new Error(`Geometrias municipais ausentes: ${missing.join(", ")}.`);

  return {
    type: "FeatureCollection",
    features: features.sort((left, right) =>
      left.properties.code.localeCompare(right.properties.code),
    ),
  };
}

export async function downloadRmrGeography(
  fetchImpl = fetch,
  municipalities = officialMunicipalities,
) {
  const responses = await Promise.all(
    municipalities.map(async ({ code }) => {
      const url = `${BASE_URL}/${code}?formato=application%2Fvnd.geo%2Bjson&qualidade=minima&periodo=${PERIOD}`;
      const response = await fetchImpl(url);
      if (!response.ok)
        throw new Error(`IBGE retornou HTTP ${response.status} para ${code}.`);
      return response.json();
    }),
  );
  return buildRmrFeatureCollection(responses, municipalities);
}

export function makeMetadata(
  geoJsonBytes,
  municipalities = officialMunicipalities,
) {
  return {
    source: "Instituto Brasileiro de Geografia e Estatística (IBGE)",
    sourceUrls: [
      "https://www.ibge.gov.br/geociencias/organizacao-do-territorio/estrutura-territorial/18354-recortes-metropolitanos-e-aglomeracoes-urbanas.html",
      "https://servicodados.ibge.gov.br/api/docs/malhas?versao=3",
      ...municipalities.map(
        ({ code }) =>
          `${BASE_URL}/${code}?formato=application%2Fvnd.geo%2Bjson&qualidade=minima&periodo=${PERIOD}`,
      ),
    ],
    compositionReference:
      "RMR conforme LC-PE 426/2020 e lista de 14 municípios publicada pelo IBGE em 17/11/2020",
    geometryPeriod: PERIOD,
    simplification:
      "Qualidade mínima entregue pela API oficial do IBGE; nenhuma simplificação adicional foi aplicada.",
    attribution:
      "Fonte: IBGE. Malha municipal simplificada para visualização. Regiões metropolitanas são definidas por lei estadual.",
    municipalityCodes: municipalities.map(({ code }) => code).sort(),
    featureCount: municipalities.length,
    geojsonSha256: hash(geoJsonBytes),
  };
}

async function validateExisting() {
  const bytes = await readFile(geoJsonPath);
  const geoJson = JSON.parse(bytes.toString("utf8"));
  buildRmrFeatureCollection([geoJson]);
  const metadata = JSON.parse(await readFile(metadataPath, "utf8"));
  if (metadata.geojsonSha256 !== hash(bytes))
    throw new Error("Checksum SHA-256 do GeoJSON não confere.");
  if (metadata.featureCount !== officialMunicipalities.length)
    throw new Error("Quantidade de feições no metadata incorreta.");
  console.log(
    `GeoJSON válido: ${geoJson.features.length} municípios; SHA-256 ${metadata.geojsonSha256}.`,
  );
}

async function main() {
  if (process.argv.includes("--download")) {
    const geoJson = await downloadRmrGeography();
    const bytes = Buffer.from(`${JSON.stringify(geoJson)}\n`, "utf8");
    const metadata = makeMetadata(bytes);
    await mkdir(outputDirectory, { recursive: true });
    await writeFile(geoJsonPath, bytes);
    await writeFile(
      metadataPath,
      `${JSON.stringify(metadata, null, 2)}\n`,
      "utf8",
    );
    console.log(
      `Gerados ${geoJson.features.length} municípios; SHA-256 ${metadata.geojsonSha256}.`,
    );
    return;
  }
  await validateExisting();
}

if (
  process.argv[1] &&
  path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)
) {
  main().catch((error) => {
    console.error(error.message);
    process.exitCode = 1;
  });
}
