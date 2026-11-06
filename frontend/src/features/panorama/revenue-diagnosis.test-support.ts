const SNAPSHOT = {
  billed_amount: null,
  billed_energy_kwh: null,
  measured_energy_kwh: null,
  observed_price_brl_per_kwh: null,
  billed_uc_count: null,
  status: "empty",
  limitations: [],
};
const COVERAGE = {
  status: "unavailable",
  covered_months: [],
  missing_months: [],
  limitations: [],
};

export const WINDOWS = ["2022-07", "2023-06", "2025-07", "2026-06"];
/** Mesma identidade do fixture Gold do Panorama, que carrega antes do bloco. */
export const PUBLICATION = {
  lote: "batch-panorama-ui",
  fingerprint: "b".repeat(64),
};

export function revenueWindow(overrides: Record<string, unknown> = {}) {
  return {
    status: "available",
    windows: WINDOWS,
    method: "PARES_MES_UC_PRECO_OBSERVADO_VOLUME_INTERACAO_V3",
    components: {
      volume: -402,
      preco: 1081,
      interacao: -66,
      entradas: 42,
      saidas: 0,
      sem_leitura: 174,
      outros: -33,
    },
    total_change_brl: 796,
    residual_brl: 0,
    group_count: 10,
    incomplete_groups: 0,
    limitations: [],
    ...overrides,
  };
}

export function revenueDiagnosis(overrides: Record<string, unknown> = {}) {
  return {
    status: "available",
    volume_offset_percent: 37.2,
    population: null,
    concentration: null,
    gd: {
      status: "unavailable",
      cohorts: [],
      share_negative_volume_percent: null,
      limitations: [],
    },
    limitations: [],
    ...overrides,
  };
}

/** Texto que aparece na tela, sem o valor exato reservado ao leitor de tela. */
export function visibleText(element: Element) {
  const clone = element.cloneNode(true) as Element;
  clone.querySelectorAll(".sr-only").forEach((hidden) => hidden.remove());
  return clone.textContent?.replaceAll(" ", " ");
}

/** Resposta crua de GET /api/v1/revenue, para passar pelo decoder real. */
export function revenueResponse(
  url: URL,
  {
    window = revenueWindow(),
    diagnosis = revenueDiagnosis(),
  }: {
    window?: Record<string, unknown> | null;
    diagnosis?: Record<string, unknown> | null;
  } = {},
) {
  const start = url.searchParams.get("competencia_inicio") ?? "2026-06";
  const end = url.searchParams.get("competencia_fim") ?? "2026-06";
  const snapshot = { ...SNAPSHOT, competencia: end };
  return {
    data: {
      currency_unit: "BRL",
      energy_unit: "kWh",
      total_billed_amount: null,
      total_paid_amount: null,
      total_measured_energy_kwh: null,
      total_billed_energy_kwh: null,
      observed_price_brl_per_kwh: null,
      series: [],
      diagnosis,
      comparison: {
        initial: snapshot,
        final: snapshot,
        billed_amount_change_brl: null,
        billed_energy_change_kwh: null,
        measured_energy_change_kwh: null,
        billed_amount_change_percent: null,
      },
      window_decomposition: window,
      window_breakdown: [],
      price_volume: {
        method: "endpoint_price_volume",
        reference_version: "gold-csv-v2",
        price_effect_brl: null,
        volume_effect_brl: null,
        interaction_effect_brl: null,
        rounding_adjustment_brl: null,
        status: "unavailable",
        limitations: [],
      },
      coverage: {
        requested_months: [],
        billed_amount: COVERAGE,
        billed_energy_kwh: COVERAGE,
        paid_amount: COVERAGE,
        measured_energy_kwh: COVERAGE,
      },
      quality: {
        small_base_threshold_uc: 5,
        small_base: false,
        percent_change_eligible: false,
        limitations: [],
      },
      breakdown: {
        dimension: url.searchParams.get("group_by") ?? "municipio",
        items: [],
        reconciliation: {
          status: "partial",
          initial_known_sum_brl: null,
          final_known_sum_brl: null,
          comparable_change_sum_brl: null,
          non_comparable_group_count: 0,
          unattributed_change_brl: null,
          residual_brl: null,
          limitations: [],
        },
      },
      filter_options: { municipios: [], bairros: [], classes: [] },
    },
    metadata: {
      contract_version: "1.1.0",
      status: "partial",
      period: { start, end, granularity: "month" },
      filters: {
        municipio: url.searchParams.get("municipio"),
        bairro: null,
        classe: url.searchParams.get("classe"),
        alimentador: null,
      },
      source: {
        kind: "gold_csv",
        version: `gold-csv-v2:${PUBLICATION.lote}:publicacao-teste`,
        publication_lote: PUBLICATION.lote,
        publication_fingerprint: PUBLICATION.fingerprint,
        is_demo: false,
        updated_at: "2026-10-29T10:00:00Z",
      },
      limitations: [],
    },
  };
}
