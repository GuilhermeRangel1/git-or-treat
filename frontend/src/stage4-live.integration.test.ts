import { expect, it } from "vitest";
import { decodeGoldMetadata } from "./shared/analytics/goldContract";
import {
  acceptGoldPublication,
  resetGoldPublication,
  withGoldPublication,
} from "./shared/analytics/goldPublication";
import { decodePanorama } from "./shared/analytics/panoramaContract";
import type { PanoramaFilters } from "./shared/analytics/types";
import { decodeQueue } from "./features/inspecoes/contract";
import { decodeOperationOptions } from "./features/operacao/useOperations";
import { decodeGoldOperationSummary } from "./features/operacao/gold-contract";

const api = import.meta.env.VITE_STAGE4_API_URL
  ? `${import.meta.env.VITE_STAGE4_API_URL.replace(/\/$/, "")}/api/v1`
  : null;
const readToken = import.meta.env.VITE_STAGE4_READ_TOKEN;
async function get(path: string) {
  if (!api || !readToken) throw new Error("Live Gold validation is disabled.");
  const response = await fetch(`${api}${path}`, {
    headers: {
      Authorization: `Bearer ${readToken}`,
    },
  });
  expect(response.status).toBe(200);
  return response.json();
}

it.skipIf(!api || !readToken)(
  "decodifica respostas reais Gold v2 das três jornadas no mesmo lote",
  async () => {
    resetGoldPublication();
    const filters: PanoramaFilters = {
      periodo: "2026-06",
      comparacao: "nenhuma",
      municipio: "todos",
      classe: "todas",
    };
    const panoramaRaw = await get(
      "/panorama?comparacao=nenhuma&municipio=todos&classe=todas",
    );
    const panorama = decodePanorama(panoramaRaw, filters, true);
    const metadata = decodeGoldMetadata(panoramaRaw.metadata);
    expect(metadata.schema_version).toBe("gold-csv-v2");
    expect(acceptGoldPublication(metadata)).toBe(true);

    const queueParams = withGoldPublication(
      new URLSearchParams("page=1&page_size=20"),
    );
    const queueRaw = await get(`/inspections/queue?${queueParams}`);
    const queue = decodeQueue(queueRaw);
    const queueMetadata = decodeGoldMetadata(queueRaw.metadata);

    const optionsRaw = await get("/operations/options");
    const options = decodeOperationOptions(optionsRaw);
    const optionsMetadata = decodeGoldMetadata(optionsRaw.metadata);
    const month = options.competencias.at(-1);
    expect(month).toBeDefined();
    const summaryParams = withGoldPublication(
      new URLSearchParams({ periodo: month! }),
    );
    const summaryRaw = await get(`/operations/summary?${summaryParams}`);
    const summary = decodeGoldOperationSummary(summaryRaw, {
      start: month!,
      end: month!,
      feederId: null,
      municipality: null,
    });

    expect(panorama.origem?.version).toBe(metadata.source.version);
    expect(queueMetadata.source.version).toBe(metadata.source.version);
    expect(queueMetadata.fingerprint).toBe(metadata.fingerprint);
    expect(optionsMetadata.source.version).toBe(metadata.source.version);
    expect(optionsMetadata.fingerprint).toBe(metadata.fingerprint);
    expect(queue.data.items).toHaveLength(20);
    expect(
      queue.data.items.every(
        (item) => item.potential_recoverable_energy_kwh === null,
      ),
    ).toBe(true);
    expect(options.competencias.length).toBeGreaterThan(0);
    expect(summary.metadata.source.version).toBe(metadata.source.version);
    expect(summary.metadata.fingerprint).toBe(metadata.fingerprint);
  },
);
