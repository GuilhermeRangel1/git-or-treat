import assert from "node:assert/strict";
import test from "node:test";
import { readFile } from "node:fs/promises";

import {
  buildRmrFeatureCollection,
  downloadRmrGeography,
  makeMetadata,
  officialMunicipalities,
} from "./prepare-rmr-geography.mjs";

const rectangle = {
  type: "Polygon",
  coordinates: [
    [
      [-35, -8],
      [-34, -8],
      [-34, -7],
      [-35, -7],
      [-35, -8],
    ],
  ],
};

function sourceFeature(code, geometry = rectangle) {
  return { type: "Feature", properties: { codarea: code }, geometry };
}

function sourceCollections(
  codes = officialMunicipalities.map(({ code }) => code),
) {
  return codes.map((code) => ({
    type: "FeatureCollection",
    features: [sourceFeature(code)],
  }));
}

test("mantém os 14 códigos oficiais como strings e preserva nome de exibição", () => {
  assert.equal(officialMunicipalities.length, 14);
  assert.ok(
    officialMunicipalities.every(
      ({ code }) => typeof code === "string" && /^\d{7}$/.test(code),
    ),
  );
  const result = buildRmrFeatureCollection(sourceCollections());
  assert.equal(result.features.length, 14);
  assert.deepEqual(result.features[0].properties, {
    code: "2600054",
    name: "Abreu e Lima",
  });
  assert.ok(
    result.features.every(
      ({ properties }) => typeof properties.name === "string",
    ),
  );
});

test("mantém sincronizados o registro TypeScript consumido pela UI e o preparador", async () => {
  const registrySource = await readFile(
    new URL("../src/features/mapa/municipalities.ts", import.meta.url),
    "utf8",
  );
  const uiMunicipalities = [
    ...registrySource.matchAll(/code:\s*"(\d{7})",\s*name:\s*"([^"]+)"/g),
  ]
    .map(([, code, name]) => ({ code, name }))
    .sort((left, right) => left.code.localeCompare(right.code));
  assert.deepEqual(
    uiMunicipalities,
    officialMunicipalities.toSorted((left, right) =>
      left.code.localeCompare(right.code),
    ),
  );
});

test("rejeita registro com código repetido antes de aceitar geometrias", () => {
  const repeated = [...officialMunicipalities, officialMunicipalities[0]];
  assert.throws(
    () => buildRmrFeatureCollection(sourceCollections(), repeated),
    /duplicado/,
  );
});

test("rejeita geometria duplicada e deixa município ausente explícito", () => {
  const codes = officialMunicipalities.map(({ code }) => code);
  assert.throws(
    () => buildRmrFeatureCollection(sourceCollections([...codes, codes[0]])),
    /duplicada/,
  );
  assert.throws(
    () => buildRmrFeatureCollection(sourceCollections(codes.slice(1))),
    /ausentes: 2600054/,
  );
});

test("rejeita código inesperado, tipo de geometria e coordenadas inválidas", () => {
  assert.throws(
    () => buildRmrFeatureCollection(sourceCollections(["0000000"])),
    /inesperado/,
  );
  const malformed = [
    {
      type: "FeatureCollection",
      features: [
        sourceFeature("2600054", { type: "Point", coordinates: [-35, -8] }),
      ],
    },
  ];
  assert.throws(
    () => buildRmrFeatureCollection(malformed),
    /Geometria inválida/,
  );
  const invalidCoordinates = [
    {
      type: "FeatureCollection",
      features: [
        sourceFeature("2600054", {
          type: "Polygon",
          coordinates: [
            [
              [181, 0],
              [0, 1],
              [1, 0],
              [181, 0],
            ],
          ],
        }),
      ],
    },
  ];
  assert.throws(
    () => buildRmrFeatureCollection(invalidCoordinates),
    /Coordenadas ou anéis inválidos/,
  );
});

test("baixa uma resposta por código oficial e valida antes de compor o asset", async () => {
  const requested = [];
  const result = await downloadRmrGeography(async (url) => {
    requested.push(url);
    const code = url.match(/municipios\/(\d+)/)?.[1];
    return {
      ok: true,
      json: async () => ({
        type: "FeatureCollection",
        features: [sourceFeature(code)],
      }),
    };
  });
  assert.equal(requested.length, 14);
  assert.equal(result.features.length, 14);
  assert.ok(requested.every((url) => url.includes("qualidade=minima")));
});

test("interrompe a preparação quando a origem falha", async () => {
  await assert.rejects(
    downloadRmrGeography(
      async () => ({ ok: false, status: 503 }),
      officialMunicipalities.slice(0, 1),
    ),
    /HTTP 503 para 2600054/,
  );
});

test("metadata registra o checksum exato dos bytes publicados e a cobertura oficial", () => {
  const bytes = Buffer.from('{"type":"FeatureCollection","features":[]}\n');
  const metadata = makeMetadata(bytes);
  assert.equal(
    metadata.geojsonSha256,
    "6d18edfe75b3149104038dcbca4d0096bbcb923f0f9fa4b49f4815344e75bb90",
  );
  assert.equal(metadata.featureCount, 14);
  assert.equal(metadata.municipalityCodes.length, 14);
  assert.ok(metadata.sourceUrls.some((url) => url.includes("geociencias")));
});
