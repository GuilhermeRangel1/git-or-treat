import type {
  OperationDetailEnvelope,
  OperationRankingEnvelope,
  OperationSummaryEnvelope,
} from "./contract";

const definition = {
  reference: "docs/contracts/operations-dev08.md#definicao-demonstrativa",
  label:
    "Indicadores simplificados de demonstração; sem apuração regulatória oficial.",
  dec_formula:
    "Soma das durações em horas dos registros UC-interrupção / denominador de UCs do alimentador.",
  fec_formula:
    "Quantidade de registros UC-interrupção / denominador de UCs do alimentador.",
  dec_unit: "h/UC",
  fec_unit: "interrupções/UC",
  event_grain:
    "Uma ocorrência registrada corresponde a uma UC afetada; não contar apenas UCs distintas.",
  population:
    "UCs ativas do snapshot demonstrativo por alimentador; denominador configurado e constante na janela.",
  rounding:
    "Três casas decimais, conforme o contrato DEV-01; não somar valores já arredondados.",
};

const metadata = <Version extends "1.1.0" | "1.2.0">(
  version: Version,
  status: "available" | "partial" | "unavailable" | "empty",
  feeder: string | null = null,
) => ({
  contract_version: version,
  status,
  period: { start: "2025-01", end: "2025-02", granularity: "month" as const },
  filters: { municipio: null, bairro: null, classe: null, alimentador: feeder },
  source: {
    kind: "synthetic",
    version: "dev03-v1",
    is_demo: true,
    updated_at: "2026-10-21T00:00:00Z",
  },
  limitations: [],
});

export const summaryFixture: OperationSummaryEnvelope = {
  data: {
    summary: {
      period: { start: "2025-01", end: "2025-02", granularity: "month" },
      observed_period: {
        start: "2025-01",
        end: "2025-02",
        granularity: "month",
      },
      dec_hours_per_uc: 1.5,
      fec_interruptions_per_uc: 0.75,
      duration_hours_sum: 6,
      interruption_count: 3,
      denominator_uc_count: 4,
      served_uc_count: 10,
      included_uc_count: 4,
      included_feeder_ids: ["AL-01", "AL-02"],
      excluded_feeder_ids: ["AL-03"],
      status: "partial",
      limitations: ["AL-03 excluído: denominador ausente."],
      text_alternative:
        "Consolidado de 2025-01 a 2025-02: DEC 1.5 h/UC; FEC 0.75 interrupções/UC.",
    },
    definition: {
      ...definition,
      dec_formula:
        "Soma das durações originais em horas dos registros UC-interrupção / soma dos denominadores dos alimentadores incluídos.",
      fec_formula:
        "Quantidade original de registros UC-interrupção / soma dos denominadores dos alimentadores incluídos.",
      population:
        "População atendida é a contagem cadastral ativa no recorte; a base incluída é a soma dos denominadores dos alimentadores elegíveis.",
      inclusion_rule:
        "Incluir somente alimentadores com estado available em toda a janela solicitada e denominador inteiro positivo; excluir os demais e identificá-los na resposta.",
    },
  },
  metadata: metadata("1.2.0", "partial"),
};

export const rankingFixture: OperationRankingEnvelope = {
  data: {
    items: [
      {
        feeder_id: "AL-01",
        municipalities: ["Vila Nova"],
        territory_status: "single_municipality",
        dec_hours_per_uc: 1.5,
        fec_interruptions_per_uc: 1,
        interruption_count: 2,
        denominator_uc_count: 2,
        covered_uc_count: 2,
        coverage_ratio: 1,
        served_uc_count: 2,
        coverage_status: "available",
        status: "available",
        limitations: [],
        period: { start: "2025-01", end: "2025-02", granularity: "month" },
        observed_period: {
          start: "2025-01",
          end: "2025-02",
          granularity: "month",
        },
        duration_hours_sum: 3,
        text_alternative:
          "AL-01, 2025-01 a 2025-02: DEC 1.5 h/UC; FEC 1 interrupções/UC.",
        rank: 1,
      },
    ],
    excluded: [],
    metric: "dec",
    order:
      "Decrescente pelo indicador; empate desfeito pelo ID do alimentador.",
    definition,
  },
  metadata: metadata("1.1.0", "available"),
};

const point = {
  feeder_id: "AL-01",
  municipalities: ["Vila Nova"],
  territory_status: "single_municipality" as const,
  dec_hours_per_uc: 1.5,
  fec_interruptions_per_uc: 1,
  interruption_count: 2,
  denominator_uc_count: 2,
  covered_uc_count: 2,
  coverage_ratio: 1,
  served_uc_count: 2,
  coverage_status: "available" as const,
  status: "available" as const,
  limitations: [],
  period: { start: "2025-01", end: "2025-02", granularity: "month" as const },
  observed_period: {
    start: "2025-01",
    end: "2025-02",
    granularity: "month" as const,
  },
  duration_hours_sum: 3,
  text_alternative:
    "AL-01, 2025-01 a 2025-02: DEC 1.5 h/UC; FEC 1 interrupções/UC.",
};

export const detailFixture: OperationDetailEnvelope = {
  data: {
    summary: point,
    series: [
      {
        ...point,
        dec_hours_per_uc: 1,
        fec_interruptions_per_uc: 0.5,
        interruption_count: 1,
        period: { start: "2025-01", end: "2025-01", granularity: "month" },
        observed_period: {
          start: "2025-01",
          end: "2025-01",
          granularity: "month",
        },
        duration_hours_sum: 2,
      },
      {
        ...point,
        dec_hours_per_uc: 0.5,
        fec_interruptions_per_uc: 0.5,
        interruption_count: 1,
        period: { start: "2025-02", end: "2025-02", granularity: "month" },
        observed_period: {
          start: "2025-02",
          end: "2025-02",
          granularity: "month",
        },
        duration_hours_sum: 1,
      },
    ],
    occurrences: [
      {
        event_id: "EV-01",
        uc_id: "UC-01",
        feeder_id: "AL-01",
        competencia: "2025-01",
        duration_hours: 2,
      },
      {
        event_id: "EV-02",
        uc_id: "UC-02",
        feeder_id: "AL-01",
        competencia: "2025-02",
        duration_hours: 1,
      },
    ],
    definition,
  },
  pagination: { page: 1, page_size: 20, total: 2, total_pages: 1 },
  metadata: metadata("1.1.0", "available", "AL-01"),
};
