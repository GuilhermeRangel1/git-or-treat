import { expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { calculateSyntheticPanorama } from "../../shared/analytics/syntheticData";
import type { PanoramaFilters } from "../../shared/analytics/types";
import type { PanoramaInsightAnalysis } from "./insightContract";
import type { usePanoramaInsight } from "./usePanoramaInsight";
import AIInsightCard from "./AIInsightCard";

function fixture(
  periodo = "2026-06",
  comparacao: PanoramaFilters["comparacao"] = "anterior",
) {
  const filters: PanoramaFilters = {
    periodo,
    comparacao,
    municipio: "Olinda",
    classe: "todas",
  };
  const data = calculateSyntheticPanorama({ ...filters, periodo: "2024-04" });
  data.filtros = filters;
  data.origem = {
    kind: "gold",
    isDemo: false,
    version: data.loteVersao,
    contractVersion: "v1",
    limitations: [],
  };
  const metric = data.metricas.receitaFaturada;
  Object.assign(metric, {
    valorAtual: 120,
    valorAnterior: 100,
    variacaoAbsoluta: 20,
    variacaoPercentual: 20,
    baseZero: false,
  });
  const analysis: PanoramaInsightAnalysis = {
    direcao: "alta",
    variacaoPercentual: 20,
    principalContribuicao: null,
    compensacao: null,
  };
  const query = {
    isPending: false,
    isFetching: false,
    isError: false,
    error: null,
    data: {
      analysis,
      insight: { status: "answered", limitations: [], hypothesis: null },
      source: { limitacoes: [] },
    },
  } as unknown as ReturnType<typeof usePanoramaInsight>;
  return {
    filters,
    data,
    metric,
    analysis,
    query,
    onRefreshIndicators: vi.fn(),
  };
}

it.each([
  {
    period: "2026-01",
    compare: "anterior" as const,
    current: 120,
    previous: 100,
    delta: 20,
    percentage: 20,
    direction: "alta" as const,
    expected:
      /aumentou 20% de Dez\/2025 para Jan\/2026.*R\$\s*100,00 para R\$\s*120,00/,
  },
  {
    period: "2026-06",
    compare: "ano_anterior" as const,
    current: 80,
    previous: 100,
    delta: -20,
    percentage: -20,
    direction: "queda" as const,
    expected:
      /caiu 20% de Jun\/2025 para Jun\/2026.*R\$\s*100,00 para R\$\s*80,00/,
  },
  {
    period: "2026-06",
    compare: "anterior" as const,
    current: 100,
    previous: 100,
    delta: 0,
    percentage: 0,
    direction: "estavel" as const,
    expected:
      /ficou estável.*R\$\s*100,00.*não significa que todos os segmentos/,
  },
  {
    period: "2026-06",
    compare: "anterior" as const,
    current: 120,
    previous: 0,
    delta: 120,
    percentage: null,
    direction: "alta" as const,
    expected: /base de comparação é zero.*sem variação percentual/,
  },
  {
    period: "2026-06",
    compare: "anterior" as const,
    current: 120,
    previous: null,
    delta: null,
    percentage: null,
    direction: "indisponivel" as const,
    expected:
      /comparação com Mai\/2026 não está disponível.*sozinho, não indica alta ou queda/,
  },
  {
    period: "2026-06",
    compare: "nenhuma" as const,
    current: 0,
    previous: null,
    delta: null,
    percentage: null,
    direction: "indisponivel" as const,
    expected: /soma R\$\s*0,00/,
  },
])(
  "explica o recorte $period com $compare, base $previous e atual $current",
  async (item) => {
    const props = fixture(item.period, item.compare);
    Object.assign(props.metric, {
      valorAtual: item.current,
      valorAnterior: item.previous,
      variacaoAbsoluta: item.delta,
      variacaoPercentual: item.percentage,
      baseZero: item.previous === 0,
    });
    Object.assign(props.analysis, {
      direcao: item.direction,
      variacaoPercentual: item.percentage,
    });
    render(<AIInsightCard {...props} />);
    expect(screen.getByText(item.expected)).toBeVisible();
    await userEvent.click(
      screen.getByRole("button", { name: "Ver análise detalhada" }),
    );
    const modal = screen.getByRole("dialog", { name: "Insight" });
    expect(within(modal).getByText(item.expected)).toBeVisible();
    expect(
      within(modal).getByRole("button", { name: "Ver tabela" }),
    ).toBeVisible();
    expect(
      within(modal).queryByRole("region", { name: "Dado observado" }),
    ).not.toBeInTheDocument();
  },
);

it("mostra rosca ou barras na distribuição, com tabela e sem o resumo superior duplicado", async () => {
  const props = fixture();
  props.data.distribuicao = {
    dimension: "classe",
    periodo: "2026-06",
    metricId: props.metric.id,
    unidade: "R$",
    total: 120,
    completo: true,
    pontos: [
      { segmento: "Residencial", valor: 90, percentual: 75 },
      { segmento: "Comercial", valor: 30, percentual: 25 },
    ],
    composicaoReceita: {
      dimension: "classe",
      segmento: "Residencial",
      valor: 90,
      participacaoPercentual: 75,
    },
  };
  const view = render(<AIInsightCard {...props} />);
  await userEvent.click(
    screen.getByRole("button", { name: "Ver análise detalhada" }),
  );
  const modal = screen.getByRole("dialog", { name: "Insight" });
  expect(within(modal).getAllByRole("img")).toHaveLength(2);
  expect(within(modal).getByText(/Residencial concentra 75%/)).toBeVisible();
  expect(within(modal).getByText(/aumentou 20%/)).toBeVisible();
  expect(
    within(modal).getAllByRole("button", { name: "Ver tabela" }),
  ).toHaveLength(2);
  expect(modal.querySelectorAll('circle[pathLength="100"]')).toHaveLength(2);
  props.data.distribuicao.completo = false;
  view.rerender(<AIInsightCard {...props} />);
  expect(within(modal).getAllByRole("img")).toHaveLength(2);
  expect(modal.querySelectorAll('circle[pathLength="100"]')).toHaveLength(0);
  expect(
    within(modal).queryByRole("region", { name: "Dado observado" }),
  ).not.toBeInTheDocument();
  expect(within(modal).getByText(/aumentou 20%/)).toBeVisible();
});

it("recomenda um caminho possível quando município e classe já estão selecionados", async () => {
  const props = fixture();
  props.filters.classe = "Residencial";
  render(<AIInsightCard {...props} />);
  expect(screen.getByText(/acompanhe este mesmo recorte/)).toBeVisible();
  await userEvent.click(
    screen.getByRole("button", { name: "Ver análise detalhada" }),
  );
  expect(
    within(screen.getByRole("dialog", { name: "Insight" })).getByText(
      /Acompanhe Residencial em Olinda.*retire um filtro por vez/,
    ),
  ).toBeVisible();
});
