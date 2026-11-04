import { describe, expect, it } from "vitest";
import { decodePanorama } from "./panoramaContract";
import type { PanoramaFilters } from "./types";

const filters: PanoramaFilters = {
  periodo: "2026-06",
  comparacao: "anterior",
  municipio: "todos",
  classe: "todas",
};

function goldMetric(id: string, status: string, value: number | null) {
  return {
    id,
    nome: id,
    categoria: "financeiro",
    tipoGrandeza: "faturado",
    valorAtual: value,
    valorAnterior: null,
    variacaoAbsoluta: null,
    variacaoPercentual: null,
    unidade: "R$",
    definicao: "Definição",
    formula: "fórmula",
    baseZero: false,
    bomSentido: "positivo",
    status,
    limitacoes: status === "unavailable" ? ["Não publicado"] : [],
    statusComparacao: "empty",
    limitacoesComparacao: ["Referência ausente"],
  };
}

function response(periodo = filters.periodo) {
  const metricas: Record<string, ReturnType<typeof goldMetric>> = {};
  const keys = [
    "receitaFaturada",
    "receitaPaga",
    "energiaConsumida",
    "energiaFaturada",
    "precoMedioEfetivo",
    "ucsAtivas",
    "continuidadeDec",
    "continuidadeFec",
    "ucsFaturadasNoMes",
  ];
  for (const key of keys) metricas[key] = goldMetric(key, "unavailable", null);
  metricas.receitaFaturada = goldMetric("rec_fat", "available", 0);
  metricas.energiaConsumida = goldMetric("ene_con", "partial", null);
  return {
    data: {
      filtros: { ...filters, periodo },
      periodoIncompleto: false,
      fechamentoMensalDeclarado: false,
      totalRegistros: 1,
      dataAtualizacao: "2026-10-29T10:00:00Z",
      loteVersao: "gold-batch-1",
      metricas,
      serieMensal: [
        {
          competencia: periodo,
          label: "Jun/26",
          receitaFaturada: 0,
          receitaPaga: null,
          energiaConsumidaKwh: null,
          energiaFaturadaKwh: null,
          ucsAtivas: null,
          decHoras: null,
          fecVezes: null,
          status: "partial",
        },
      ],
      opcoesFiltros: {
        competencias: [periodo],
        municipios: ["Curitiba"],
        classes: ["Residencial"],
      },
    },
    metadata: {
      contract_version: "2.0.0",
      status: "partial",
      period: { start: periodo, end: periodo, granularity: "month" },
      filters: {
        municipio: null,
        bairro: null,
        classe: null,
        alimentador: null,
      },
      source: {
        kind: "gold",
        version: "gold-batch-1",
        is_demo: false,
        updated_at: "2026-10-29T10:00:00Z",
      },
      limitations: ["Fechamento mensal não declarado"],
      temporal_scope: "monthly",
      schema_version: "gold-csv-v2",
      fingerprint: "a".repeat(64),
    },
  };
}

describe("decodePanorama Gold v2", () => {
  it("preserva zero, nulos, opções reais e origem da publicação", () => {
    const decoded = decodePanorama(response(), filters);
    expect(decoded.metricas.receitaFaturada.valorAtual).toBe(0);
    expect(decoded.metricas.energiaConsumida.valorAtual).toBeNull();
    expect(decoded.serieMensal[0].receitaFaturada).toBe(0);
    expect(decoded.serieMensal[0].energiaConsumidaKwh).toBeNull();
    expect(decoded.opcoesFiltros?.municipios).toEqual(["Curitiba"]);
    expect(decoded.origem).toMatchObject({
      kind: "gold",
      fingerprint: "a".repeat(64),
    });
  });

  it("só aceita competência observada diferente durante bootstrap", () => {
    expect(() => decodePanorama(response("2026-05"), filters)).toThrow();
    expect(
      decodePanorama(response("2026-05"), filters, true).filtros.periodo,
    ).toBe("2026-05");
  });

  it("recusa esquema antigo e metadados de filtros divergentes", () => {
    const oldSchema = response();
    oldSchema.metadata.schema_version = "gold-csv-v1";
    expect(() => decodePanorama(oldSchema, filters)).toThrow();

    const mismatchedFilter = response();
    (mismatchedFilter.metadata.filters as Record<string, unknown>).municipio =
      "Recife";
    expect(() => decodePanorama(mismatchedFilter, filters)).toThrow();
  });
});
