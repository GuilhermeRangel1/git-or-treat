import { describe, expect, it } from "vitest";
import {
  decodeOperationDetail,
  decodeOperationRanking,
  decodeOperationSummary,
  OperationContractError,
} from "./contract";
import {
  detailFixture,
  rankingFixture,
  summaryFixture,
} from "./fixtures.test-support";
import {
  decodeGoldOperationSummary,
  decodeGoldOperationRanking,
  decodeGoldOperationDetail,
} from "./gold-contract";

const goldMetadata = {
  contract_version: "2.0.0",
  status: "partial",
  period: { start: "2025-01", end: "2025-02", granularity: "month" },
  filters: { municipio: null, bairro: null, classe: null, alimentador: null },
  source: {
    kind: "gold",
    version: "batch-1",
    is_demo: false,
    updated_at: "2026-10-29T00:00:00Z",
  },
  limitations: [],
  temporal_scope: "monthly",
  schema_version: "gold-csv-v2",
  fingerprint: "a".repeat(64),
};
const goldDefinition = {
  reference: "docs/dicionario_gold.md",
  dec_formula: "duração/base",
  fec_formula: "frequência/base",
  dec_unit: "h/UC",
  fec_unit: "int./UC",
  event_grain: "UC-interrupção",
  population: "cadastro atual",
  completeness: "completude não comprovada",
};
const goldPoint = {
  feeder_id: "F-1",
  municipality: "Recife",
  period: goldMetadata.period,
  observed_period: goldMetadata.period,
  observed_competencies: ["2025-01", "2025-02"],
  missing_competencies: [],
  duration_hours_sum: 8,
  interruption_count: null,
  denominator_uc_count: 4,
  dec_hours_per_uc: 2,
  fec_interruptions_per_uc: null,
  status: "partial",
  dec_status: "partial",
  fec_status: "unavailable",
  limitations: ["FEC ausente"],
};

describe("contratos de Operação", () => {
  it("decodifica Gold v2 com bases e estados DEC/FEC independentes e detalhe agregado", () => {
    const summary = decodeGoldOperationSummary(
      {
        metadata: goldMetadata,
        data: {
          period: goldMetadata.period,
          observed_period: goldMetadata.period,
          duration_hours_sum: 8,
          interruption_count: null,
          denominator_uc_count: null,
          dec_hours_per_uc: 2,
          fec_interruptions_per_uc: null,
          dec_denominator_uc_count: 4,
          fec_denominator_uc_count: null,
          dec_included_feeder_ids: ["F-1"],
          fec_included_feeder_ids: [],
          dec_excluded_feeder_ids: [],
          fec_excluded_feeder_ids: ["F-1"],
          included_feeder_ids: null,
          excluded_feeder_ids: null,
          dec_status: "partial",
          fec_status: "unavailable",
          status: "partial",
          limitations: ["Bases diferentes"],
        },
        definition: goldDefinition,
      },
      { start: "2025-01", end: "2025-02", feederId: null, municipality: null },
    );
    expect(summary.data.summary.dec_denominator_uc_count).toBe(4);
    expect(summary.data.summary.fec_status).toBe("unavailable");
    expect(summary.data.summary.denominator_uc_count).toBeNull();

    const ranking = decodeGoldOperationRanking(
      {
        metadata: goldMetadata,
        data: {
          items: [{ ...goldPoint, municipality: null, rank: 1 }],
          excluded: [],
          metric: "dec",
          order: "DEC descendente",
          definition: goldDefinition,
        },
      },
      "dec",
      { start: "2025-01", end: "2025-02", feederId: null, municipality: null },
    );
    expect(ranking.data.items[0].fec_interruptions_per_uc).toBeNull();
    expect(ranking.data.items[0].municipality).toBeNull();
    expect(ranking.data.items[0].feeder_id).toBe("F-1");
    const detail = decodeGoldOperationDetail(
      {
        metadata: {
          ...goldMetadata,
          filters: { ...goldMetadata.filters, alimentador: "F-1" },
        },
        data: {
          summary: goldPoint,
          series: [
            {
              ...goldPoint,
              period: {
                start: "2025-01",
                end: "2025-01",
                granularity: "month",
              },
            },
          ],
          occurrences: null,
          occurrences_status: "unavailable",
          definition: goldDefinition,
        },
      },
      { feederId: "F-1", start: "2025-01", end: "2025-02", municipality: null },
    );
    expect(detail.data.occurrences).toBeNull();
    expect(detail.data.summary.fec_status).toBe("unavailable");
  });
  it("preserva zero conhecido e recusa schema físico anterior ao v2", () => {
    const response = {
      metadata: goldMetadata,
      data: {
        items: [
          {
            ...goldPoint,
            duration_hours_sum: 0,
            interruption_count: 0,
            dec_hours_per_uc: 0,
            fec_interruptions_per_uc: 0,
            status: "available",
            dec_status: "available",
            fec_status: "available",
            rank: 1,
          },
        ],
        excluded: [],
        metric: "dec",
        order: "DEC descendente",
        definition: goldDefinition,
      },
    };
    const decoded = decodeGoldOperationRanking(response, "dec", {
      start: "2025-01",
      end: "2025-02",
      feederId: null,
      municipality: null,
    });
    expect(decoded.data.items[0].dec_hours_per_uc).toBe(0);
    expect(decoded.data.items[0].fec_interruptions_per_uc).toBe(0);

    expect(() =>
      decodeGoldOperationRanking(
        {
          ...response,
          metadata: { ...goldMetadata, schema_version: "gold-csv-v1" },
        },
        "dec",
        {
          start: "2025-01",
          end: "2025-02",
          feederId: null,
          municipality: null,
        },
      ),
    ).toThrow(/Metadados Gold inválidos/);
  });
  it("decodifica summary parcial canônico, preservando valores e exclusões", () => {
    expect(decodeOperationSummary(summaryFixture)).toEqual(summaryFixture);
  });

  it("aceita zero conhecido e indisponibilidade explicitamente nula", () => {
    const zero = structuredClone(summaryFixture);
    zero.data.summary.dec_hours_per_uc = 0;
    zero.data.summary.fec_interruptions_per_uc = 0;
    zero.data.summary.duration_hours_sum = 0;
    zero.data.summary.interruption_count = 0;
    zero.data.summary.status = "available";
    zero.data.summary.excluded_feeder_ids = [];
    zero.data.summary.included_feeder_ids = ["AL-01"];
    zero.data.summary.denominator_uc_count = 2;
    zero.data.summary.included_uc_count = 2;
    zero.metadata.status = "available";
    expect(decodeOperationSummary(zero).data.summary.dec_hours_per_uc).toBe(0);

    const unavailable = structuredClone(summaryFixture);
    unavailable.data.summary.dec_hours_per_uc = null;
    unavailable.data.summary.fec_interruptions_per_uc = null;
    unavailable.data.summary.duration_hours_sum = null;
    unavailable.data.summary.interruption_count = null;
    unavailable.data.summary.denominator_uc_count = null;
    unavailable.data.summary.included_feeder_ids = [];
    unavailable.data.summary.included_uc_count = 0;
    unavailable.data.summary.status = "unavailable";
    unavailable.metadata.status = "unavailable";
    expect(
      decodeOperationSummary(unavailable).data.summary.denominator_uc_count,
    ).toBeNull();
  });

  it("rejeita número não finito, versão, campo obrigatório ou estado contraditório", () => {
    const notFinite = structuredClone(summaryFixture);
    notFinite.data.summary.dec_hours_per_uc = Number.NaN;
    expect(() => decodeOperationSummary(notFinite)).toThrow(
      OperationContractError,
    );

    const wrongVersion = structuredClone(summaryFixture);
    (
      wrongVersion as unknown as { metadata: { contract_version: string } }
    ).metadata.contract_version = "1.1.0";
    expect(() => decodeOperationSummary(wrongVersion)).toThrow(
      /contract_version/,
    );

    const missing = structuredClone(summaryFixture) as unknown as Record<
      string,
      unknown
    >;
    delete (missing.metadata as Record<string, unknown>).source;
    expect(() => decodeOperationSummary(missing)).toThrow(/metadata.source/);

    const impossible = structuredClone(summaryFixture);
    impossible.data.summary.denominator_uc_count = null;
    expect(() => decodeOperationSummary(impossible)).toThrow(/all totals/i);

    const incomplete = structuredClone(summaryFixture);
    incomplete.data.summary.interruption_count = null;
    expect(() => decodeOperationSummary(incomplete)).toThrow(/all totals/i);

    const duplicateIds = structuredClone(summaryFixture);
    duplicateIds.data.summary.included_feeder_ids = ["AL-01", "AL-01"];
    expect(() => decodeOperationSummary(duplicateIds)).toThrow(
      /unique and disjoint/i,
    );

    const overlapIds = structuredClone(summaryFixture);
    overlapIds.data.summary.excluded_feeder_ids = ["AL-01"];
    expect(() => decodeOperationSummary(overlapIds)).toThrow(
      /unique and disjoint/i,
    );
  });

  it("decodifica ranking e detalhe completos, incluindo ocorrências e paginação", () => {
    expect(decodeOperationRanking(rankingFixture)).toEqual(rankingFixture);
    expect(decodeOperationDetail(detailFixture)).toEqual(detailFixture);
  });

  it("rejeita item sem campos, métrica divergente ou paginação inválida", () => {
    const missing = structuredClone(rankingFixture);
    delete (
      missing.data.items[0] as Partial<(typeof missing.data.items)[number]>
    ).rank;
    expect(() => decodeOperationRanking(missing)).toThrow(/rank/);

    const wrongMetric = structuredClone(rankingFixture);
    wrongMetric.data.metric = "fec";
    expect(() => decodeOperationRanking(wrongMetric, "dec")).toThrow(/métrica/);

    const wrongPagination = structuredClone(detailFixture);
    wrongPagination.pagination.page_size = 0;
    expect(() => decodeOperationDetail(wrongPagination)).toThrow(/pagination/);
  });

  it("preserva denominador negativo indisponível e páginas vazias após o total", () => {
    const unavailable = structuredClone(detailFixture);
    unavailable.data.summary.status = "unavailable";
    unavailable.data.summary.coverage_status = "unavailable";
    unavailable.data.summary.dec_hours_per_uc = null;
    unavailable.data.summary.fec_interruptions_per_uc = null;
    unavailable.data.summary.denominator_uc_count = -1;
    unavailable.data.series = [];
    unavailable.data.occurrences = [];
    unavailable.metadata.status = "unavailable";
    expect(
      decodeOperationDetail(unavailable).data.summary.denominator_uc_count,
    ).toBe(-1);

    const beyondLastPage = structuredClone(detailFixture);
    beyondLastPage.pagination.page = 10;
    beyondLastPage.data.occurrences = [];
    expect(decodeOperationDetail(beyondLastPage).pagination.page).toBe(10);
  });

  it("restringe os estados do ranking e a série mensal ao alimentador do detalhe", () => {
    const partialRanked = structuredClone(rankingFixture);
    partialRanked.data.items[0].status = "partial";
    expect(() => decodeOperationRanking(partialRanked)).toThrow(
      /available feeders/,
    );

    const availableExcluded = structuredClone(rankingFixture);
    availableExcluded.data.excluded = [availableExcluded.data.items[0]];
    expect(() => decodeOperationRanking(availableExcluded)).toThrow(
      /cannot contain available/,
    );

    const wrongFeederSeries = structuredClone(detailFixture);
    wrongFeederSeries.data.series[0].feeder_id = "AL-02";
    expect(() => decodeOperationDetail(wrongFeederSeries)).toThrow(
      /another feeder/,
    );

    const outsideSeries = structuredClone(detailFixture);
    outsideSeries.data.series[0].period = {
      start: "2024-12",
      end: "2024-12",
      granularity: "month",
    };
    expect(() => decodeOperationDetail(outsideSeries)).toThrow(
      /outside the requested/,
    );
  });
});
