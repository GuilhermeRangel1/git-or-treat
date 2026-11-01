import { describe, expect, it } from "vitest";
import { decodeAIQuestionResponse } from "./contract";

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
