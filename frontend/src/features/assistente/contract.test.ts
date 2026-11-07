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

  it("deriva resposta, tabela e gráfico das linhas exatas da evidência", () => {
    const result = decodeSqlAnalysisResponse(sqlResponse);
    expect(result).toMatchObject({
      status: "answered",
      sql_analysis_mode: true,
      audit_reference: sqlResponse.audit_reference,
      answer: sqlResponse.presentation.answer,
      sql_presentation: sqlResponse.presentation,
      visualization: {
        kind: "bars",
        points: [
          { observation_id: "row_1", label: "Recife", value: 1234.5 },
          { observation_id: "row_2", label: "Olinda", value: 975.25 },
        ],
      },
    });
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
});
