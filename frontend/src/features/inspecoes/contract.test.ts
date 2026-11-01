import { describe, expect, it } from "vitest";
import { decodeDetail, decodeQueue } from "./contract";

const metadata = {
  contract_version: "2.0.0",
  status: "available",
  period: null,
  filters: { municipio: null, bairro: null, classe: null, alimentador: null },
  source: {
    kind: "gold",
    version: "batch-2026-10",
    is_demo: false,
    updated_at: "2026-10-29T12:00:00Z",
  },
  limitations: ["Snapshot cadastral."],
  temporal_scope: "snapshot",
  schema_version: "gold-csv-v2",
  fingerprint: "a".repeat(64),
};
const goldItem = {
  queue_position: 7,
  uc_id: "UC-123",
  municipality: "Recife",
  neighborhood: null,
  class_name: "Residencial",
  feeder_id: null,
  category: "REVISAR",
  reason: "REVISAR",
  potential_recoverable_energy_kwh: null,
  recovery_unavailable_reason: "A Gold não publica estimativa de recuperação.",
  evidence: {
    inspections_performed: 0,
    confirmed_irregular_inspections: null,
    historical_average_kwh_per_reading: 0,
    distributed_generation_present: null,
    cadastral_status: "ATIVA",
    call_center_contacts: 2,
    interruptions: null,
  },
  variation: {
    p1_start: "2022-07",
    p1_end: "2023-06",
    p1_months_observed: 0,
    p1_average_kwh_per_month: null,
    p2_start: "2025-07",
    p2_end: "2026-06",
    p2_months_observed: 12,
    p2_average_kwh_per_month: 0,
    variation_kwh: null,
    variation_pct: null,
    drop_over_30_pct: null,
  },
};

describe("contrato Gold da fila de inspeções", () => {
  it("mantém categoria e evidências Gold sem score, estimativa ou período mensal inventado", () => {
    const decoded = decodeQueue({
      data: {
        items: [goldItem],
        filter_options: {
          municipio: ["Recife"],
          bairro: [],
          classe: ["Residencial"],
          alimentador: [],
        },
        summary: {
          total_units: 1,
          categories: { REVISAR: 1 },
          uncategorized_units: 0,
          estimated_units: 0,
          unavailable_estimate_units: 1,
        },
      },
      pagination: { page: 1, page_size: 10, total: 1, total_pages: 1 },
      metadata,
    });

    expect(decoded.metadata).toMatchObject({
      contract_version: "2.0.0",
      period: null,
      temporal_scope: "snapshot",
      fingerprint: "a".repeat(64),
    });
    expect(decoded.data.items[0]).toMatchObject({
      category: "REVISAR",
      queue_position: 7,
      potential_recoverable_energy_kwh: null,
      recovery_unavailable_reason:
        "A Gold não publica estimativa de recuperação.",
      evidence: { inspections_performed: 0 },
      variation: { p1_months_observed: 0, p1_average_kwh_per_month: null },
    });
  });

  it("decodifica detalhe Gold sem converter variação ou evidências ausentes em zero", () => {
    const decoded = decodeDetail({
      data: {
        ...goldItem,
        rule_version: "gold-fila-inspecao-v1",
        limitations: ["Categoria não é prioridade de despacho."],
      },
      metadata,
    });

    expect(decoded.data).toMatchObject({
      category: "REVISAR",
      queue_position: 7,
      rule_version: "gold-fila-inspecao-v1",
      variation: { variation_kwh: null, variation_pct: null },
      evidence: { confirmed_irregular_inspections: null },
    });
  });

  it("preserva a comparação trimestral proposta no detalhe Gold", () => {
    const decoded = decodeDetail({
      data: {
        ...goldItem,
        rule_version: "gold-fila-inspecao-v1",
        limitations: [],
        consumption_comparison: {
          baseline_start: "2024-08",
          baseline_end: "2024-10",
          recent_start: "2024-11",
          recent_end: "2025-01",
          baseline_kwh: 300,
          recent_kwh: 150,
          change_percent: -50,
          unavailable_reason: null,
        },
      },
      metadata,
    });
    expect(decoded.data.consumption_comparison).toMatchObject({
      baseline_kwh: 300,
      recent_kwh: 150,
      change_percent: -50,
    });
  });

  it("requires a positive integer queue position in Gold details", () => {
    expect(() =>
      decodeDetail({
        data: {
          ...goldItem,
          queue_position: -1,
          rule_version: "gold-fila-inspecao-v1",
          limitations: [],
        },
        metadata,
      }),
    ).toThrow();
    expect(() =>
      decodeDetail({
        data: {
          ...goldItem,
          queue_position: 0,
          rule_version: "gold-fila-inspecao-v1",
          limitations: [],
        },
        metadata,
      }),
    ).toThrow();
    expect(() =>
      decodeDetail({
        data: {
          ...goldItem,
          queue_position: 1.5,
          rule_version: "gold-fila-inspecao-v1",
          limitations: [],
        },
        metadata,
      }),
    ).toThrow();
    expect(() =>
      decodeDetail({
        data: {
          ...goldItem,
          queue_position: undefined,
          rule_version: "gold-fila-inspecao-v1",
          limitations: [],
        },
        metadata,
      }),
    ).toThrow();
  });

  it("accepts negative variation while rejecting negative source values", () => {
    const variation = {
      ...goldItem.variation,
      p1_months_observed: 1,
      p1_average_kwh_per_month: 100,
      p2_months_observed: 1,
      p2_average_kwh_per_month: 80,
      variation_kwh: -20,
      variation_pct: -20,
    };
    const decoded = decodeDetail({
      data: {
        ...goldItem,
        variation,
        rule_version: "gold-fila-inspecao-v1",
        limitations: [],
      },
      metadata,
    });

    expect(
      "variation" in decoded.data ? decoded.data.variation : undefined,
    ).toMatchObject({
      variation_kwh: -20,
      variation_pct: -20,
    });
    for (const field of [
      "p1_months_observed",
      "p1_average_kwh_per_month",
      "p2_months_observed",
      "p2_average_kwh_per_month",
    ] as const) {
      expect(() =>
        decodeDetail({
          data: {
            ...goldItem,
            variation: { ...variation, [field]: -1 },
            rule_version: "gold-fila-inspecao-v1",
            limitations: [],
          },
          metadata,
        }),
      ).toThrow();
    }
  });
});
