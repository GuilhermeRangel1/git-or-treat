import { describe, expect, it } from "vitest";
import { decodeAIQuestionResponse } from "./contract";
import { visualResponse, points } from "./visualization.test-support";
describe("visualização do chat", () => {
  it("decodifica pontos estruturados sem analisar números da prosa", () => {
    expect(
      decodeAIQuestionResponse(visualResponse).visualization?.points.map(
        (p) => p.value,
      ),
    ).toEqual([100, 120, 110]);
  });
  it.each([
    { unit: "kWh" },
    { period: "2026-05" },
    { kind: "script" },
    {
      points: [
        ...points,
        { observation_id: "row_999", label: "inventado", value: 1 },
      ],
    },
    { plot_points: [{ ...points[0], value: 999 }] },
  ])("recusa formato, unidade, período ou pontos adulterados", (patch) => {
    expect(() =>
      decodeAIQuestionResponse({
        ...visualResponse,
        visualization: { ...visualResponse.visualization, ...patch },
      }),
    ).toThrow();
  });
  it("não admite visualização em resposta conceitual ou recusa", () => {
    expect(() =>
      decodeAIQuestionResponse({
        ...visualResponse,
        evidence: [
          {
            source: "documentation.indicators",
            description: "Definição interna.",
            is_demo: false,
          },
        ],
      }),
    ).toThrow();
  });
});
