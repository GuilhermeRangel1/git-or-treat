import { describe, expect, it } from "vitest";
import { decodeAIQuestionResponse } from "./contract";
import { visualResponse, points } from "./visualization.test-support";
import { chatChartPoints } from "./visualization";
describe("visualização do chat", () => {
  it("preserva os 14 grupos na tabela e agrupa a rosca em seis setores", () => {
    const all = Array.from({ length: 14 }, (_, i) => ({
      observation_id: `row_${i + 1}`,
      label: `Grupo ${i + 1}`,
      value: i + 1,
    }));
    const decoded = decodeAIQuestionResponse({
      ...visualResponse,
      visualization: {
        ...visualResponse.visualization,
        kind: "donut",
        total: 105,
        sectors: [
          ...all
            .slice(9)
            .reverse()
            .map((p) => ({
              label: p.label,
              value: p.value,
              percentage: (p.value / 105) * 100,
              observation_ids: [p.observation_id],
            })),
          {
            label: "Demais grupos (9)",
            value: 45,
            percentage: (45 / 105) * 100,
            observation_ids: all.slice(0, 9).map((p) => p.observation_id),
          },
        ],
        points: all,
        plot_points: all,
      },
    }).visualization!;
    const data = chatChartPoints(decoded, (value) => value);
    expect(data.total).toBe(105);
    expect(data.tablePoints).toHaveLength(14);
    expect(data.points).toHaveLength(6);
    expect(data.points.at(-1)).toMatchObject({
      label: "Demais grupos (9)",
      value: 45,
    });
    expect(data.points.reduce((sum, p) => sum + p.value, 0)).toBe(105);
    expect(
      data.points.reduce(
        (sum, p) => sum + ("percentage" in p ? p.percentage : 0),
        0,
      ),
    ).toBeCloseTo(100);
  });
  it.each([
    [-1, 5],
    [0, 0],
  ])("recusa rosca com parcelas incompatíveis: %j", (...values) => {
    const all = values.map((value, i) => ({
      observation_id: `row_${i + 1}`,
      label: `Grupo ${i}`,
      value,
    }));
    expect(() =>
      decodeAIQuestionResponse({
        ...visualResponse,
        visualization: {
          ...visualResponse.visualization,
          kind: "donut",
          points: all,
          plot_points: all,
        },
      }),
    ).toThrow();
  });
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
