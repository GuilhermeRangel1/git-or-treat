import { describe, expect, it } from "vitest";
import { decodeDistribution } from "./distributionContract";
import type { KpiMetric, PanoramaFilters } from "./types";
const filters: PanoramaFilters = {
  periodo: "2026-06",
  comparacao: "nenhuma",
  municipio: "todos",
  classe: "Residencial",
};
const metric = {
  id: "rec_fat",
  unidade: "R$",
  valorAtual: 100,
  status: "available",
} as KpiMetric;
const partition = {
  dimension: "municipio",
  periodo: "2026-06",
  metricId: "rec_fat",
  unidade: "R$",
  total: 100,
  completo: true,
  pontos: [
    { segmento: "A", valor: 30, percentual: 30 },
    { segmento: "B", valor: 70, percentual: 70 },
  ],
};
describe("distribuição do Panorama", () => {
  it("aceita apenas partição reconciliada da mesma métrica e período", () => {
    expect(decodeDistribution(partition, filters, metric)).toEqual(partition);
  });
  it.each([
    { periodo: "2026-05" },
    { unidade: "kWh" },
    { dimension: "classe" },
    { total: 101 },
    {
      pontos: [
        { segmento: "A", valor: 29, percentual: 30 },
        partition.pontos[1],
      ],
    },
    {
      pontos: [{ ...partition.pontos[0], percentual: 40 }, partition.pontos[1]],
    },
  ])("recusa mudança de contexto ou pontos: %j", (patch) => {
    expect(() =>
      decodeDistribution({ ...partition, ...patch }, filters, metric),
    ).toThrow();
  });
  it("não amplia recorte com classe e município específicos", () => {
    expect(() =>
      decodeDistribution(partition, { ...filters, municipio: "A" }, metric),
    ).toThrow();
  });
  it("permite valores observados incompletos com barras, sem percentuais", () => {
    const value = {
      ...partition,
      completo: false,
      pontos: partition.pontos.map((p) => ({ ...p, percentual: null })),
    };
    expect(decodeDistribution(value, filters, metric)).toEqual(value);
  });
});

it("valida Demais municípios contra toda a lista e recusa resumo adulterado", () => {
  const pontos = Array.from({ length: 200 }, (_, i) => ({
    segmento: `Município de teste ${i + 1}`,
    valor: 200 - i,
    percentual: Number((((200 - i) / 20100) * 100).toFixed(2)),
  }));
  const visual = [
    ...pontos.slice(0, 5),
    { segmento: "Demais municípios (195)", valor: 19110, percentual: 95.07 },
  ];
  const value = { ...partition, total: 20100, pontos, visual, agrupados: 195 };
  const current = { ...metric, valorAtual: 20100 };
  expect(decodeDistribution(value, filters, current)?.pontos).toHaveLength(200);
  expect(() =>
    decodeDistribution(
      {
        ...value,
        visual: [...visual.slice(0, 5), { ...visual[5], valor: 19111 }],
      },
      filters,
      current,
    ),
  ).toThrow();
});
