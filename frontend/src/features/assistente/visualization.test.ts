import { describe, expect, it } from "vitest";
import {
  decodeAIQuestionResponse,
  type SqlAnalysisPresentation,
} from "./contract";
import { visualResponse, points } from "./visualization.test-support";
import { chatChartPoints, sqlAnalysisVisualization } from "./visualization";
describe("visualização do chat", () => {
  it("omite gráfico temporal quando a série tem lacunas ou não está ordenada", () => {
    const presentation: SqlAnalysisPresentation = {
      contract_version: "text-to-sql-f1-presentation-v1",
      state: "ready",
      operation: "monthly_series",
      answer: "Série mensal.",
      period: "2026-01 a 2026-03",
      filters: [],
      universe: [],
      limitations: [],
      columns: [
        {
          key: "competency",
          label: "Competência",
          role: "dimension",
          semantic_id: "competency",
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
        { observation_id: "row_1", cells: ["2026-01-01", "1.00"] },
        { observation_id: "row_2", cells: ["2026-03-01", "3.00"] },
      ],
      evidence_digest: "a".repeat(64),
    };
    expect(sqlAnalysisVisualization(presentation)).toBeUndefined();
    expect(
      sqlAnalysisVisualization({
        ...presentation,
        rows: [...presentation.rows].reverse(),
      }),
    ).toBeUndefined();
  });

  it("omite gráficos quando a precisão excede o limite seguro do navegador", () => {
    const presentation: SqlAnalysisPresentation = {
      contract_version: "text-to-sql-f1-presentation-v1",
      state: "ready",
      operation: "grouped_total",
      answer: "Faturamento por município.",
      period: "2026-01",
      filters: [],
      universe: ["Municípios: todos os valores disponíveis no recorte"],
      limitations: [],
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
        {
          observation_id: "row_1",
          cells: ["Recife", "9007199254740993.00"],
        },
      ],
      evidence_digest: "a".repeat(64),
    };
    expect(sqlAnalysisVisualization(presentation)).toBeUndefined();
  });

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
