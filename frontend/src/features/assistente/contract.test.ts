import { describe, expect, it } from "vitest";
import {
  decodeAIQuestionResponse,
  decodeSqlAnalysisResponse,
} from "./contract";

const answered = {
  contract_version: "v1",
  correlation_id: "0123456789abcdef0123456789abcdef",
  status: "answered",
  answer: "O consumo demonstrativo aumentou no período informado.",
  message: null,
  evidence: [
    {
      source: "synthetic.fixture",
      description: "Cenário artificial de consumo.",
      is_demo: true,
    },
  ],
  limitations: ["Valores fictícios."],
  analysis_context: {
    metric: "Consumo",
    unit: "kWh fictícios",
    period: "2025-01 a 2025-02",
    filters: { municipio: "Exemplo" },
  },
};

describe("contrato de perguntas do chat", () => {
  it("recusa rótulos de filtros que não pertencem ao recorte aplicado", () => {
    expect(() =>
      decodeAIQuestionResponse({
        ...answered,
        analysis_context: {
          ...answered.analysis_context,
          filter_labels: { outro: "Outro" },
        },
      }),
    ).toThrow("Resposta inválida do serviço.");
  });
  it("aceita resposta v1 fundamentada e marcada como demonstrativa", () => {
    expect(decodeAIQuestionResponse(answered)).toMatchObject({
      contract_version: "v1",
      status: "answered",
      answer: "O consumo demonstrativo aumentou no período informado.",
      evidence: [{ is_demo: true }],
    });
  });

  it("recusa uma resposta quantitativa sem evidência", () => {
    expect(() =>
      decodeAIQuestionResponse({ ...answered, evidence: [] }),
    ).toThrow("Resposta inválida do serviço.");
  });

  it("aceita esclarecimento como estado distinto de resposta", () => {
    expect(
      decodeAIQuestionResponse({
        contract_version: "v1",
        status: "needs_clarification",
        answer: null,
        message: "Qual período você quer consultar?",
        evidence: [],
        limitations: [],
      }),
    ).toMatchObject({ status: "needs_clarification", evidence: [] });
  });

  it("recusa versões e estados desconhecidos", () => {
    expect(() =>
      decodeAIQuestionResponse({ ...answered, contract_version: "v2" }),
    ).toThrow("Resposta inválida do serviço.");
    expect(() =>
      decodeAIQuestionResponse({ ...answered, status: "unknown" }),
    ).toThrow("Resposta inválida do serviço.");
  });
});

describe("resposta apresentada pela F1 Text-to-SQL", () => {
  const sqlResponse = {
    correlation_id: "0123456789abcdef0123456789abcdef",
    audit_reference: "abcdef0123456789abcdef0123456789",
    status: "answered",
    evidence: {
      evidence_contract_version: "text-to-sql-f1-evidence-v1",
      source_table: "gold_v2.diagnostico_receita",
      metric_id: "billing.revenue",
      coverage_quality: "certified",
      batch_ref:
        "gold-csv-v2:GOLD_20261106T000000Z_aaaaaaaa:12345678-1234-4123-8123-123456789abc",
      evidence_digest: "a".repeat(64),
      columns: [
        { name: "municipality", role: "dimension", unit: null },
        { name: "revenue", role: "measure", unit: "R$" },
      ],
      rows: [
        ["Recife", "1234.50"],
        ["Olinda", "975.25"],
      ],
    },
    presentation: {
      contract_version: "text-to-sql-f1-presentation-v1",
      state: "ready",
      operation: "grouped_total",
      answer: "O faturamento por município está detalhado na tabela.",
      period: "2025-01 a 2025-12",
      filters: ["Classe de consumo: Residencial"],
      universe: ["Municípios: todos os valores disponíveis no recorte"],
      limitations: [
        "Faturamento representa valor faturado e não confirma recebimento ou pagamento.",
      ],
      columns: [
        {
          key: "municipality",
          label: "Município",
          role: "dimension",
          semantic_id: "municipality",
          unit: null,
        },
        {
          key: "revenue",
          label: "Faturamento",
          role: "measure",
          semantic_id: "revenue_total",
          unit: "R$",
        },
      ],
      rows: [
        { observation_id: "row_1", cells: ["Recife", "1234.50"] },
        { observation_id: "row_2", cells: ["Olinda", "975.25"] },
      ],
      evidence_digest: "a".repeat(64),
    },
  };

  it("decodifica resposta composta com origem Gold e staging do histórico F1", () => {
    const response = decodeSqlAnalysisResponse({
      correlation_id: "0123456789abcdef0123456789abcdef",
      audit_reference: "abcdef0123456789abcdef0123456789",
      status: "answered",
      evidence: null,
      presentation: null,
      clarification: null,
      unsupported_reason: null,
      continuation_token: "signed-continuation-token",
      compound_analysis: {
        contract_version: "text-to-sql-f1-compound-v1",
        answer: "A comparação foi concluída.",
        active_gold_batch:
          "gold-csv-v2:GOLD_20261103T173853Z_76c37784:12345678-1234-4123-8123-123456789abc",
        staging_manifest_digest: "a".repeat(64),
        staging_csv_digest: "b".repeat(64),
        method: "PARES_MES_UC_PRECO_OBSERVADO_VOLUME_INTERACAO_V3",
        windows: {
          p0_start: "2024-07",
          p0_end: "2025-06",
          p1_start: "2025-07",
          p1_end: "2026-06",
          method: "PARES_MES_UC_PRECO_OBSERVADO_VOLUME_INTERACAO_V3",
        },
        municipalities: [
          {
            municipality: "Recife",
            previous_consumption_kwh: "100.0",
            current_consumption_kwh: "80.0",
            change_kwh: "-20.0",
            change_percent: "-20.000000",
            revenue_by_class: [
              {
                neighborhood: "Centro",
                consumption_class: "RESIDENCIAL",
                variation_brl: "12.50",
                volume_effect_brl: "-3.00",
                price_effect_brl: "14.00",
                interaction_effect_brl: "1.50",
                state: "CALCULADA_BASE_COMUM",
              },
              {
                neighborhood: "Várzea",
                consumption_class: "INDUSTRIAL",
                variation_brl: "-2.25",
                volume_effect_brl: null,
                price_effect_brl: null,
                interaction_effect_brl: null,
                state: "SEM_BASE_COMUM",
              },
            ],
          },
        ],
        limitations: [
          "A decomposição foi lida de staging local Gold v2, não é Gold ativa.",
          "Consumo e faturamento vêm de agregações independentes.",
        ],
        evidence_digest: "c".repeat(64),
      },
    });

    expect(response).toMatchObject({
      status: "answered",
      sql_analysis_mode: true,
      continuation_token: "signed-continuation-token",
      sql_compound_analysis: {
        municipalities: [
          {
            municipality: "Recife",
            revenue_by_class: [
              { state: "CALCULADA_BASE_COMUM" },
              { state: "SEM_BASE_COMUM", volume_effect_brl: null },
            ],
          },
        ],
      },
      evidence: [{ source: "gold.local" }, { source: "gold-v2.staging" }],
    });
  });

  it("deriva resposta, tabela e gráfico das linhas exatas da evidência", () => {
    const result = decodeSqlAnalysisResponse(sqlResponse);
    expect(result).toMatchObject({
      status: "answered",
      sql_analysis_mode: true,
      audit_reference: sqlResponse.audit_reference,
      answer: sqlResponse.presentation.answer,
      sql_presentation: sqlResponse.presentation,
      visualization: {
        kind: "horizontal",
        points: [
          { observation_id: "row_1", label: "Recife", value: 1234.5 },
          { observation_id: "row_2", label: "Olinda", value: 975.25 },
        ],
      },
    });
  });

  it("aceita receita por bairro como dimensão da evidência Gold", () => {
    const neighborhoodResponse = JSON.parse(JSON.stringify(sqlResponse));
    neighborhoodResponse.evidence.source_table =
      "gold_v2.consumo_receita_bairro";
    neighborhoodResponse.evidence.columns[0].name = "neighborhood";
    neighborhoodResponse.evidence.rows = [["Boa Vista", "12.50"]];
    neighborhoodResponse.presentation.columns[0] = {
      key: "neighborhood",
      label: "Bairro",
      role: "dimension",
      semantic_id: "neighborhood",
      unit: null,
    };
    neighborhoodResponse.presentation.rows = [
      { observation_id: "row_1", cells: ["Boa Vista", "12.50"] },
    ];
    const decoded = decodeSqlAnalysisResponse(neighborhoodResponse);
    expect(decoded.sql_presentation?.columns[0].semantic_id).toBe(
      "neighborhood",
    );
  });

  it("aceita atendimento acumulado sem inventar período", () => {
    const accumulatedResponse = JSON.parse(JSON.stringify(sqlResponse));
    accumulatedResponse.evidence.evidence_contract_version =
      "text-to-sql-f1-evidence-v6";
    accumulatedResponse.evidence.source_table = "gold_v2.visao_360_uc";
    accumulatedResponse.evidence.metric_id = "service.accumulated_attendance";
    accumulatedResponse.evidence.columns = [
      { name: "attendance", role: "measure", unit: "protocolos" },
    ];
    accumulatedResponse.evidence.rows = [["42"]];
    accumulatedResponse.evidence.measure_semantics = {
      attendance: "attendance_accumulated_total",
    };
    accumulatedResponse.evidence.dimension_semantics = {};
    accumulatedResponse.evidence.interpretation = {
      metric_id: "service.accumulated_attendance",
      operation: "accumulated_total",
      aggregation: "sum",
      periods: [],
      filters: [],
      group_by: [],
      ranking_direction: null,
      ranking_limit: null,
    };
    accumulatedResponse.presentation = {
      contract_version: "text-to-sql-f1-presentation-v5",
      state: "ready",
      operation: "accumulated_total",
      answer: "No histórico publicado, foram registrados 42 protocolos.",
      period: "Histórico acumulado",
      filters: [],
      universe: [],
      limitations: [
        "Histórico publicado sem intervalo conhecido ou certificação de completude histórica.",
      ],
      columns: [
        {
          key: "attendance",
          label: "Chamados no histórico",
          role: "measure",
          semantic_id: "attendance_accumulated_total",
          unit: "protocolos",
        },
      ],
      rows: [{ observation_id: "row_1", cells: ["42"] }],
      evidence_digest: "a".repeat(64),
    };
    const decoded = decodeSqlAnalysisResponse(accumulatedResponse);
    expect(decoded).toMatchObject({
      status: "answered",
      sql_presentation: {
        period: "Histórico acumulado",
        operation: "accumulated_total",
      },
    });
  });

  it("aceita uma comparação financeira com somente as métricas pedidas", () => {
    const comparison = {
      correlation_id: sqlResponse.correlation_id,
      audit_reference: sqlResponse.audit_reference,
      status: "answered",
      evidence: null,
      presentation: null,
      clarification: null,
      unsupported_reason: null,
      continuity_pair_analysis: null,
      compound_analysis: {
        contract_version: "text-to-sql-f1-financial-comparison-v1",
        answer: "De janeiro a junho, o consumo caiu e o preço observado subiu.",
        active_gold_batch:
          "gold-csv-v2:GOLD_20261106T000000Z_aaaaaaaa:12345678-1234-4123-8123-123456789abc",
        municipality: "RECIFE",
        start_month: "2026-01",
        end_month: "2026-06",
        metric_ids: ["energy.consumption", "billing.effective_tariff"],
        monthly: [
          {
            period: "2026-01",
            consumption_kwh: "7622382",
            revenue_brl: null,
            observed_price_brl_per_kwh: "0.7547",
          },
          {
            period: "2026-06",
            consumption_kwh: "5353512",
            revenue_brl: null,
            observed_price_brl_per_kwh: "0.7557",
          },
        ],
        limitations: ["Preço observado não é tarifa regulada."],
        evidence_digest: "c".repeat(64),
      },
    };
    const decoded = decodeSqlAnalysisResponse(comparison);
    expect(decoded).toMatchObject({ status: "answered", sql_analysis_mode: true });
    expect(decoded.sql_financial_comparison?.metric_ids).toEqual([
      "energy.consumption", "billing.effective_tariff",
    ]);
    expect(decoded.sql_financial_comparison?.monthly).toEqual([
      expect.objectContaining({
        period: "2026-01", consumption_kwh: "7622382", revenue_brl: null,
      }),
      expect.objectContaining({
        period: "2026-06", consumption_kwh: "5353512", revenue_brl: null,
      }),
    ]);
  });

  it("aceita a apresentação v2 com crescimento percentual derivado no Backend", () => {
    const result = decodeSqlAnalysisResponse({
      ...sqlResponse,
      evidence: {
        ...sqlResponse.evidence,
        evidence_contract_version: "text-to-sql-f1-evidence-v2",
        columns: [
          { name: "period_0", role: "measure", unit: "R$" },
          { name: "period_1", role: "measure", unit: "R$" },
          { name: "difference", role: "measure", unit: "R$" },
          { name: "period_0_growth_percent", role: "measure", unit: "%" },
        ],
        rows: [["150.03", "80.00", "70.03", "87.54"]],
      },
      presentation: {
        ...sqlResponse.presentation,
        contract_version: "text-to-sql-f1-presentation-v2",
        operation: "comparison",
        columns: [
          {
            key: "period_0",
            label: "Faturamento no período 1",
            role: "measure",
            semantic_id: "period_0_total",
            unit: "R$",
          },
          {
            key: "period_1",
            label: "Faturamento no período 2",
            role: "measure",
            semantic_id: "period_1_total",
            unit: "R$",
          },
          {
            key: "difference",
            label: "Diferença",
            role: "measure",
            semantic_id: "period_0_minus_period_1",
            unit: "R$",
          },
          {
            key: "period_0_growth_percent",
            label: "Variação percentual",
            role: "measure",
            semantic_id: "period_0_growth_percent",
            unit: "%",
          },
        ],
        rows: [
          {
            observation_id: "row_1",
            cells: ["150.03", "80.00", "70.03", "87.54"],
          },
        ],
      },
    });

    const columns = result.sql_presentation?.columns ?? [];
    expect(columns[columns.length - 1]).toMatchObject({
      semantic_id: "period_0_growth_percent",
      unit: "%",
    });
  });

  it("preserva comparação agrupada v2 como tabela sem gráfico enganoso", () => {
    const result = decodeSqlAnalysisResponse({
      ...sqlResponse,
      evidence: {
        ...sqlResponse.evidence,
        evidence_contract_version: "text-to-sql-f1-evidence-v2",
        columns: [
          { name: "municipality", role: "dimension", unit: null },
          { name: "period_0", role: "measure", unit: "R$" },
          { name: "period_1", role: "measure", unit: "R$" },
          { name: "difference", role: "measure", unit: "R$" },
          { name: "period_0_growth_percent", role: "measure", unit: "%" },
        ],
        rows: [["Recife", "150.03", "80.00", "70.03", "87.54"]],
      },
      presentation: {
        ...sqlResponse.presentation,
        contract_version: "text-to-sql-f1-presentation-v2",
        operation: "comparison",
        columns: [
          {
            key: "municipality",
            label: "Município",
            role: "dimension",
            semantic_id: "municipality",
            unit: null,
          },
          {
            key: "period_0",
            label: "Faturamento no período 1",
            role: "measure",
            semantic_id: "period_0_total",
            unit: "R$",
          },
          {
            key: "period_1",
            label: "Faturamento no período 2",
            role: "measure",
            semantic_id: "period_1_total",
            unit: "R$",
          },
          {
            key: "difference",
            label: "Diferença",
            role: "measure",
            semantic_id: "period_0_minus_period_1",
            unit: "R$",
          },
          {
            key: "period_0_growth_percent",
            label: "Variação percentual",
            role: "measure",
            semantic_id: "period_0_growth_percent",
            unit: "%",
          },
        ],
        rows: [
          {
            observation_id: "row_1",
            cells: ["Recife", "150.03", "80.00", "70.03", "87.54"],
          },
        ],
      },
    });

    expect(result.sql_presentation?.operation).toBe("comparison");
    expect(result.sql_presentation?.rows[0].cells).toEqual([
      "Recife",
      "150.03",
      "80.00",
      "70.03",
      "87.54",
    ]);
    expect(result.visualization).toBeUndefined();
  });

  it("aceita contagem de protocolos apresentada pela evidência v4", () => {
    const result = decodeSqlAnalysisResponse({
      ...sqlResponse,
      evidence: {
        ...sqlResponse.evidence,
        evidence_contract_version: "text-to-sql-f1-evidence-v4",
        source_table: "gold_v2.atendimentos_uc",
        metric_id: "service.attendance",
        columns: [{ name: "attendance", role: "measure", unit: "protocolos" }],
        rows: [["6433"]],
      },
      presentation: {
        ...sqlResponse.presentation,
        contract_version: "text-to-sql-f1-presentation-v3",
        operation: "total",
        answer: "Foram abertos 6.433 protocolos no período junho de 2026.",
        period: "2026-06",
        filters: [],
        universe: [],
        limitations: [],
        columns: [
          {
            key: "attendance",
            label: "Protocolos abertos",
            role: "measure",
            semantic_id: "attendance_total",
            unit: "protocolos",
          },
        ],
        rows: [{ observation_id: "row_1", cells: ["6433"] }],
      },
    });
    expect(result).toMatchObject({
      status: "answered",
      analysis_context: {
        metric: "service.attendance",
        metric_label: "Protocolos de atendimento",
        unit: "protocolos",
      },
    });
    expect(result.visualization).toBeUndefined();
  });

  it("aceita média mensal de satisfação na unidade pontos", () => {
    const result = decodeSqlAnalysisResponse({
      ...sqlResponse,
      evidence: {
        ...sqlResponse.evidence,
        evidence_contract_version: "text-to-sql-f1-evidence-v7",
        source_table: "gold_v2.atendimentos_uc",
        metric_id: "service.satisfaction",
        interpretation: {
          metric_id: "service.satisfaction",
          operation: "average",
          aggregation: "average_non_null",
          periods: [{ start: "2026-06-01", end: "2026-06-30" }],
          filters: [],
          group_by: [],
          ranking_direction: null,
          ranking_limit: null,
        },
        columns: [{ name: "satisfaction", role: "measure", unit: "pontos" }],
        measure_semantics: { satisfaction: "satisfaction_average" },
        rows: [["4.25"]],
      },
      presentation: {
        ...sqlResponse.presentation,
        contract_version: "text-to-sql-f1-presentation-v6",
        operation: "average",
        answer:
          "A nota média de satisfação no período junho de 2026 foi 4,25 pontos.",
        period: "2026-06",
        filters: [],
        universe: [],
        limitations: [
          "Média das notas informadas; valores ausentes são excluídos e zero é válido.",
        ],
        columns: [
          {
            key: "satisfaction",
            label: "Nota média de satisfação",
            role: "measure",
            semantic_id: "satisfaction_average",
            unit: "pontos",
          },
        ],
        rows: [{ observation_id: "row_1", cells: ["4.25"] }],
      },
    });
    expect(result).toMatchObject({
      status: "answered",
      analysis_context: {
        metric: "service.satisfaction",
        metric_label: "Nota média de satisfação",
        unit: "pontos",
      },
    });
  });

  it("aceita retrato do cadastro de UCs com GD no lote publicado", () => {
    const result = decodeSqlAnalysisResponse({
      ...sqlResponse,
      evidence: {
        ...sqlResponse.evidence,
        evidence_contract_version: "text-to-sql-f1-evidence-v8",
        source_table: "gold_v2.variacao_consumo_uc",
        metric_id: "energy.gd_units",
        interpretation: {
          metric_id: "energy.gd_units",
          operation: "snapshot_total",
          aggregation: "count_non_null",
          periods: [],
          filters: [
            {
              dimension_id: "generation.distributed",
              operator: "eq",
              values: ["Sim"],
            },
          ],
          group_by: [],
          ranking_direction: null,
          ranking_limit: null,
        },
        columns: [
          {
            name: "gd_units",
            role: "measure",
            value_type: "integer",
            unit: "UCs",
          },
        ],
        measure_semantics: { gd_units: "gd_units_total" },
        rows: [["42"]],
      },
      presentation: {
        ...sqlResponse.presentation,
        contract_version: "text-to-sql-f1-presentation-v7",
        operation: "snapshot_total",
        answer:
          "Foram identificadas 42 UCs com GD cadastrada no lote publicado.",
        period: "Cadastro de GD no lote",
        filters: [],
        universe: [],
        limitations: [
          "Retrato do cadastro no lote publicado; não informa quando a GD entrou em operação nem confirma geração ou injeção.",
        ],
        columns: [
          {
            key: "gd_units",
            label: "UCs com GD cadastrada",
            role: "measure",
            semantic_id: "gd_units_total",
            unit: "UCs",
          },
        ],
        rows: [{ observation_id: "row_1", cells: ["42"] }],
      },
    });
    expect(result).toMatchObject({
      status: "answered",
      analysis_context: {
        metric: "energy.gd_units",
        metric_label: "UCs com GD cadastrada",
        unit: "UCs",
      },
    });
  });

  it("aceita satisfação média no histórico sem inventar período", () => {
    const result = decodeSqlAnalysisResponse({
      ...sqlResponse,
      evidence: {
        ...sqlResponse.evidence,
        evidence_contract_version: "text-to-sql-f1-evidence-v9",
        source_table: "gold_v2.atendimentos_uc",
        metric_id: "service.accumulated_satisfaction",
        interpretation: {
          metric_id: "service.accumulated_satisfaction",
          operation: "accumulated_average",
          aggregation: "average_non_null",
          periods: [],
          filters: [],
          group_by: [],
          ranking_direction: null,
          ranking_limit: null,
        },
        columns: [
          {
            name: "satisfaction",
            role: "measure",
            value_type: "decimal",
            unit: "pontos",
          },
        ],
        measure_semantics: { satisfaction: "satisfaction_accumulated_average" },
        rows: [["4.25"]],
      },
      presentation: {
        ...sqlResponse.presentation,
        contract_version: "text-to-sql-f1-presentation-v8",
        operation: "accumulated_average",
        answer:
          "A média das notas individuais válidas no histórico publicado foi 4,25 pontos. O intervalo e a completude histórica não são conhecidos.",
        period: "Histórico acumulado",
        filters: [],
        universe: [],
        limitations: [
          "Média das notas válidas do histórico publicado; o intervalo e a completude histórica não são conhecidos.",
        ],
        columns: [
          {
            key: "satisfaction",
            label: "Nota média de satisfação no histórico",
            role: "measure",
            semantic_id: "satisfaction_accumulated_average",
            unit: "pontos",
          },
        ],
        rows: [{ observation_id: "row_1", cells: ["4.25"] }],
      },
    });
    expect(result).toMatchObject({
      status: "answered",
      analysis_context: {
        metric: "service.accumulated_satisfaction",
        metric_label: "Nota média de satisfação no histórico",
        unit: "pontos",
      },
    });
  });

  it("aceita DEC observacional com o aviso de cobertura não certificada", () => {
    const result = decodeSqlAnalysisResponse({
      ...sqlResponse,
      evidence: {
        ...sqlResponse.evidence,
        evidence_contract_version: "text-to-sql-f1-evidence-v5",
        source_table: "gold_v2.indicadores_dec_fec",
        metric_id: "network.equivalent_interruption_duration",
        coverage_quality: "observed_uncertified",
        interpretation: {
          metric_id: "network.equivalent_interruption_duration",
          operation: "grain_read",
          aggregation: "key_grain_read",
          periods: [{ start: "2026-06-01", end: "2026-06-30" }],
          filters: [
            {
              dimension_id: "network.feeder",
              operator: "eq",
              values: ["ALIM-01"],
            },
          ],
        },
        columns: [{ name: "value", role: "measure", unit: "horas por UC" }],
        rows: [["1.25"]],
      },
      presentation: {
        ...sqlResponse.presentation,
        contract_version: "text-to-sql-f1-presentation-v4",
        operation: "grain_read",
        answer:
          "DEC no período junho de 2026 (Alimentador: ALIM-01): 1,25 horas por UC. Valores observados; cobertura do alimentador não certificada.",
        period: "2026-06",
        filters: ["Alimentador: ALIM-01"],
        universe: [],
        limitations: [
          "Valores observados; cobertura do alimentador não certificada.",
        ],
        columns: [
          {
            key: "value",
            label: "DEC",
            role: "measure",
            semantic_id: "dec_value",
            unit: "horas por UC",
          },
        ],
        rows: [{ observation_id: "row_1", cells: ["1.25"] }],
      },
    });
    expect(result.analysis_context).toMatchObject({
      metric: "network.equivalent_interruption_duration",
      metric_label: "DEC",
      unit: "horas por UC",
    });
    expect(result.answer).toContain("cobertura do alimentador não certificada");
    expect(result.visualization).toBeUndefined();
  });

  it("aceita DEC ponderado com população elegível e excluída na evidência", () => {
    const warning =
      "Valores observados; cobertura do alimentador não certificada.";
    const result = decodeSqlAnalysisResponse({
      ...sqlResponse,
      evidence: {
        ...sqlResponse.evidence,
        evidence_contract_version: "text-to-sql-f1-evidence-v12",
        source_table: "gold_v2.indicadores_dec_fec",
        metric_id: "network.equivalent_interruption_duration",
        coverage_quality: "observed_uncertified",
        interpretation: {
          metric_id: "network.equivalent_interruption_duration",
          operation: "weighted_continuity",
          aggregation: "weighted_ratio",
          periods: [{ start: "2025-01-01", end: "2025-03-31" }],
          filters: [],
        },
        columns: [
          { name: "dec_value", role: "measure", unit: "horas por UC" },
          { name: "feeders_included", role: "measure", unit: "alimentadores" },
          { name: "feeders_excluded", role: "measure", unit: "alimentadores" },
        ],
        measure_semantics: {
          dec_value: "dec_value",
          feeders_included: "feeders_included",
          feeders_excluded: "feeders_excluded",
        },
        dimension_semantics: {},
        rows: [["1.25", "3", "2"]],
      },
      presentation: {
        ...sqlResponse.presentation,
        contract_version: "text-to-sql-f1-presentation-v11",
        state: "ready",
        operation: "weighted_continuity",
        answer: `DEC ponderado em janeiro a março de 2025: 1,25. Foram incluídos 3 alimentadores elegíveis e excluídos 2 alimentadores observados. ${warning}`,
        period: "2025-01 a 2025-03",
        filters: [],
        universe: [],
        limitations: [warning],
        columns: [
          {
            key: "dec_value",
            label: "DEC",
            role: "measure",
            semantic_id: "dec_value",
            unit: "horas por UC",
          },
          {
            key: "feeders_included",
            label: "Alimentadores elegíveis",
            role: "measure",
            semantic_id: "feeders_included",
            unit: "alimentadores",
          },
          {
            key: "feeders_excluded",
            label: "Alimentadores observados excluídos",
            role: "measure",
            semantic_id: "feeders_excluded",
            unit: "alimentadores",
          },
        ],
        rows: [{ observation_id: "row_1", cells: ["1.25", "3", "2"] }],
      },
    });
    expect(result.sql_presentation?.operation).toBe("weighted_continuity");
    expect(
      result.sql_presentation?.columns.map((column) => column.semantic_id),
    ).toEqual(["dec_value", "feeders_included", "feeders_excluded"]);
    expect(result.limitations).toContain(warning);
  });

  it("decodifica a resposta conjunta de DEC e FEC com o mesmo recorte", () => {
    const warning =
      "Valores observados; cobertura do alimentador não certificada.";
    const metricResult = (
      metricId: string,
      key: string,
      meaning: "dec_value" | "fec_value",
      unit: string,
      value: string,
      label: string,
      answer: string,
    ) => ({
      evidence: {
        ...sqlResponse.evidence,
        evidence_contract_version: "text-to-sql-f1-evidence-v12",
        source_table: "gold_v2.indicadores_dec_fec",
        metric_id: metricId,
        coverage_quality: "observed_uncertified",
        status: "available",
        interpretation: {
          metric_id: metricId,
          operation: "weighted_continuity",
          aggregation: "weighted_ratio",
          periods: [{ start: "2026-01-01", end: "2026-06-30" }],
          filters: [
            {
              dimension_id: "network.feeder",
              operator: "eq",
              values: ["ALM-ABR-001"],
            },
          ],
          group_by: [],
          ranking_direction: null,
          ranking_limit: null,
        },
        columns: [
          { name: key, role: "measure", value_type: "decimal", unit },
          { name: "feeders_included", role: "measure", value_type: "integer", unit: "alimentadores" },
          { name: "feeders_excluded", role: "measure", value_type: "integer", unit: "alimentadores" },
        ],
        measure_semantics: {
          [key]: meaning,
          feeders_included: "feeders_included",
          feeders_excluded: "feeders_excluded",
        },
        dimension_semantics: {},
        rows: [[value, "1", "0"]],
      },
      presentation: {
        ...sqlResponse.presentation,
        contract_version: "text-to-sql-f1-presentation-v11",
        state: "ready",
        operation: "weighted_continuity",
        answer,
        period: "2026-01 a 2026-06",
        filters: ["Alimentador: ALM-ABR-001"],
        universe: [],
        limitations: [warning],
        columns: [
          { key, label, role: "measure", semantic_id: meaning, unit },
          { key: "feeders_included", label: "Alimentadores elegíveis", role: "measure", semantic_id: "feeders_included", unit: "alimentadores" },
          { key: "feeders_excluded", label: "Alimentadores observados excluídos", role: "measure", semantic_id: "feeders_excluded", unit: "alimentadores" },
        ],
        rows: [{ observation_id: "row_1", cells: [value, "1", "0"] }],
      },
    });
    const dec = metricResult(
      "network.equivalent_interruption_duration",
      "dec_value",
      "dec_value",
      "horas por UC",
      "0.538505",
      "DEC",
      `DEC ponderado: 0,538505 horas por UC. ${warning}`,
    );
    const fec = metricResult(
      "network.equivalent_interruption_frequency",
      "fec_value",
      "fec_value",
      "interrupções por UC",
      "0.299645",
      "FEC",
      `FEC ponderado: 0,299645 interrupções por UC. ${warning}`,
    );
    const response = decodeSqlAnalysisResponse({
      correlation_id: sqlResponse.correlation_id,
      audit_reference: sqlResponse.audit_reference,
      status: "answered",
      continuation_token: null,
      continuity_pair_analysis: {
        contract_version: "text-to-sql-f1-continuity-pair-v1",
        answer: `${dec.presentation.answer} ${fec.presentation.answer} ${warning}`,
        active_gold_batch: sqlResponse.evidence.batch_ref,
        dec,
        fec,
        limitations: [warning],
        evidence_digest: "d".repeat(64),
      },
    });

    expect(response.sql_continuity_pair_analysis).toBeDefined();
    expect(response.evidence).toHaveLength(2);
    expect(response.limitations).toContain(warning);
  });

  it("recusa divergência entre a tabela de apresentação e a evidência", () => {
    expect(() =>
      decodeSqlAnalysisResponse({
        ...sqlResponse,
        presentation: {
          ...sqlResponse.presentation,
          evidence_digest: "b".repeat(64),
        },
      }),
    ).toThrow("Resposta Text-to-SQL inválida.");
    expect(() =>
      decodeSqlAnalysisResponse({
        ...sqlResponse,
        presentation: {
          ...sqlResponse.presentation,
          rows: [
            { observation_id: "row_1", cells: ["Recife", "9.99"] },
            { observation_id: "row_2", cells: ["Olinda", "975.25"] },
          ],
        },
      }),
    ).toThrow("Resposta Text-to-SQL inválida.");
  });

  it("recusa remoção ou alteração da ressalva semântica da métrica", () => {
    expect(() =>
      decodeSqlAnalysisResponse({
        ...sqlResponse,
        presentation: {
          ...sqlResponse.presentation,
          limitations: [],
        },
      }),
    ).toThrow("Resposta Text-to-SQL inválida.");
  });

  it("preserva esclarecimento e não suportado como estados sem números", () => {
    const clarification = decodeSqlAnalysisResponse({
      correlation_id: sqlResponse.correlation_id,
      audit_reference: sqlResponse.audit_reference,
      status: "needs_clarification",
      evidence: null,
      presentation: null,
      clarification: {
        question: "Você quer apenas janeiro a junho de 2026?",
        missing_fields: ["period"],
      },
      unsupported_reason: null,
    });
    expect(clarification).toMatchObject({
      status: "needs_clarification",
      sql_analysis_mode: true,
      evidence: [],
    });
    expect(clarification.sql_presentation).toBeUndefined();

    const unsupported = decodeSqlAnalysisResponse({
      correlation_id: sqlResponse.correlation_id,
      audit_reference: sqlResponse.audit_reference,
      status: "unsupported",
      evidence: null,
      presentation: null,
      clarification: null,
      unsupported_reason: {
        code: "operation_outside_f1",
        message: "Essa análise ainda não está disponível na F1.",
      },
    });
    expect(unsupported).toMatchObject({
      status: "refused",
      sql_analysis_mode: true,
      evidence: [],
    });
    expect(unsupported.sql_presentation).toBeUndefined();
  });

  it("mantém consulta vazia diferente de medida nula", () => {
    const measureColumn = {
      name: "revenue",
      role: "measure",
      unit: "R$",
    };
    const presentationColumn = {
      key: "revenue",
      label: "Faturamento",
      role: "measure",
      semantic_id: "revenue_total",
      unit: "R$",
    };
    const empty = decodeSqlAnalysisResponse({
      ...sqlResponse,
      evidence: {
        ...sqlResponse.evidence,
        status: "empty",
        columns: [measureColumn],
        rows: [],
      },
      presentation: {
        ...sqlResponse.presentation,
        state: "empty",
        operation: "total",
        answer: "Não há linhas de faturamento no recorte consultado.",
        columns: [presentationColumn],
        rows: [],
      },
    });
    const nullMeasure = decodeSqlAnalysisResponse({
      ...sqlResponse,
      evidence: {
        ...sqlResponse.evidence,
        status: "all_measures_null",
        columns: [measureColumn],
        rows: [[null]],
      },
      presentation: {
        ...sqlResponse.presentation,
        state: "all_measures_null",
        operation: "total",
        answer: "A fonte não trouxe valores de faturamento.",
        columns: [presentationColumn],
        rows: [{ observation_id: "row_1", cells: [null] }],
      },
    });
    expect(empty.sql_presentation?.state).toBe("empty");
    expect(empty.limitations).toContain(
      "A consulta não retornou linhas para o recorte.",
    );
    expect(nullMeasure.sql_presentation?.state).toBe("all_measures_null");
    expect(nullMeasure.limitations).toContain(
      "As linhas retornadas não contêm valores de faturamento disponíveis.",
    );
  });

  it("recusa células numéricas inválidas em vez de desenhar gráfico ou tabela falsa", () => {
    expect(() =>
      decodeSqlAnalysisResponse({
        ...sqlResponse,
        presentation: {
          ...sqlResponse.presentation,
          rows: [{ observation_id: "row_1", cells: ["Recife", "1e999"] }],
        },
      }),
    ).toThrow("Resposta Text-to-SQL inválida.");
  });

  it("aceita contagem de queda de consumo com GD nas janelas aprovadas", () => {
    const result = decodeSqlAnalysisResponse({
      ...sqlResponse,
      evidence: {
        ...sqlResponse.evidence,
        evidence_contract_version: "text-to-sql-f1-evidence-v10",
        source_table: "gold_v2.variacao_consumo_uc",
        metric_id: "energy.gd_consumption_drop",
        interpretation: {
          metric_id: "energy.gd_consumption_drop",
          operation: "snapshot_total",
          aggregation: "count_gd_drop",
          periods: [],
          filters: [
            {
              dimension_id: "generation.distributed",
              operator: "eq",
              values: ["Sim"],
            },
          ],
          group_by: [],
          ranking_direction: null,
          ranking_limit: null,
        },
        columns: [
          {
            name: "gd_drop_units",
            role: "measure",
            value_type: "integer",
            unit: "UCs",
          },
        ],
        measure_semantics: { gd_drop_units: "gd_consumption_drop_units" },
        rows: [["5"]],
      },
      presentation: {
        ...sqlResponse.presentation,
        contract_version: "text-to-sql-f1-presentation-v9",
        operation: "snapshot_total",
        answer:
          "Foram identificadas 5 UCs nas janelas fixas jul/2022–jun/2023 vs. jul/2025–jun/2026 (Geração distribuída (cadastro): Sim).",
        period: "jul/2022–jun/2023 vs. jul/2025–jun/2026",
        filters: [],
        universe: [],
        limitations: [
          "Queda bruta nas janelas fixas; exige ao menos seis meses com leitura em cada janela e não demonstra causa nem origem solar.",
        ],
        columns: [
          {
            key: "gd_drop_units",
            label: "UCs com GD e queda de consumo >30%",
            role: "measure",
            semantic_id: "gd_consumption_drop_units",
            unit: "UCs",
          },
        ],
        rows: [{ observation_id: "row_1", cells: ["5"] }],
      },
    });
    expect(result).toMatchObject({
      status: "answered",
      analysis_context: {
        metric: "energy.gd_consumption_drop",
        metric_label: "UCs com GD e queda de consumo superior a 30%",
        unit: "UCs",
      },
    });
  });
});
