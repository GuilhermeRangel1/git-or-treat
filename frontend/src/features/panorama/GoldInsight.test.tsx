import { expect, it, vi } from "vitest";
import userEvent from "@testing-library/user-event";
import { render, screen } from "@testing-library/react";
import { calculateSyntheticPanorama } from "../../shared/analytics/syntheticData";
import type { PanoramaFilters } from "../../shared/analytics/types";
import AIInsightCard from "./AIInsightCard";
import { requestPanoramaInsight, PanoramaInsightApiError } from "./insightApi";
import type { usePanoramaInsight } from "./usePanoramaInsight";

it("confere os números do KPI e apresenta Gold sem aviso demonstrativo", async () => {
  const filters: PanoramaFilters = {
    periodo: "2024-04",
    comparacao: "anterior",
    municipio: "todos",
    classe: "todas",
  };
  const data = calculateSyntheticPanorama(filters);
  data.origem = {
    kind: "gold",
    isDemo: false,
    version: data.loteVersao,
    contractVersion: "v1",
    fingerprint: "a".repeat(64),
    limitations: [],
  };
  data.periodoIncompleto = false;
  const metric = data.metricas.receitaFaturada;
  metric.status = "partial";
  metric.statusComparacao = "unavailable";
  metric.valorAnterior = null;
  metric.variacaoAbsoluta = null;
  metric.variacaoPercentual = null;
  const envelope = {
    metric: { id: metric.id, definicao: "Receita comparável", formula: "soma" },
    source: {
      fingerprint: "a".repeat(64),
      kind: "gold",
      isDemo: false,
      loteVersao: data.loteVersao,
      dataAtualizacao: data.dataAtualizacao,
      limitacoes: [],
    },
    analysis: {
      composicaoAtual: {
        dimension: "municipio",
        segmento: "Recife",
        valor: Math.round((metric.valorAtual ?? 0) * 25) / 100,
        participacaoPercentual: 25,
      },
      direcao: "indisponivel",
      variacaoPercentual: null,
      principalContribuicao: null,
      compensacao: null,
    },
    insight: {
      contract_version: "v1",
      correlation_id: "a".repeat(32),
      audit_reference: "b".repeat(32),
      status: "answered",
      error: null,
      message: null,
      context: {
        metric: "Receita comparável",
        unit: metric.unidade,
        period: {
          start: "2024-04-01",
          end: "2024-04-30",
          granularity: "month",
        },
        filters,
      },
      observation: {
        values: [
          { label: "Período atual", value: metric.valorAtual },
          {
            label: "Maior receita observada no mês · Recife",
            value: Math.round((metric.valorAtual ?? 0) * 25) / 100,
          },
        ],
      },
      hypothesis:
        "Investigue a composição deste recorte; não há causa comprovada.",
      evidence: [
        {
          source: "gold.local",
          description: "Publicação Gold controlada.",
          is_demo: false,
        },
      ],
      limitations: ["Fechamento mensal não certificado."],
    },
  };
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(new Response(JSON.stringify(envelope))),
  );
  const result = await requestPanoramaInsight(
    filters,
    data,
    new AbortController().signal,
  );
  expect(
    JSON.parse(vi.mocked(fetch).mock.calls[0][1]!.body as string).fingerprint,
  ).toBe("a".repeat(64));
  expect(
    JSON.parse(vi.mocked(fetch).mock.calls[0][1]!.body as string).filters,
  ).toEqual(filters);
  for (const changed of [
    { ...filters, periodo: "2024-03" },
    { ...filters, comparacao: "nenhuma" },
    { ...filters, municipio: "Recife" },
    { ...filters, classe: "RESIDENCIAL" },
  ]) {
    const incompatible = structuredClone(envelope);
    incompatible.insight.context.filters = changed as PanoramaFilters;
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response(JSON.stringify(incompatible))),
    );
    await expect(
      requestPanoramaInsight(filters, data, new AbortController().signal),
    ).rejects.toThrow(/incompatível/);
  }
  for (const change of [
    { participacaoPercentual: 90 },
    { valor: (metric.valorAtual ?? 0) + 1 },
    { dimension: "bairro" },
    { segmento: "Outro município" },
  ]) {
    const incompatible = structuredClone(envelope);
    Object.assign(incompatible.analysis.composicaoAtual, change);
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response(JSON.stringify(incompatible))),
    );
    await expect(
      requestPanoramaInsight(filters, data, new AbortController().signal),
    ).rejects.toThrow(/incompatível/);
  }
  envelope.source.fingerprint = "b".repeat(64);
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(new Response(JSON.stringify(envelope))),
  );
  await expect(
    requestPanoramaInsight(filters, data, new AbortController().signal),
  ).rejects.toThrow(/incompatível/);
  envelope.source.fingerprint = "a".repeat(64);
  const comparedData = structuredClone(data);
  comparedData.metricas.receitaFaturada.valorAnterior = 150;
  const comparedEnvelope = {
    ...structuredClone(envelope),
    analysis: { ...envelope.analysis, composicaoAtual: null },
  };
  comparedEnvelope.insight.observation.values[1] = {
    label: "Período comparado",
    value: 151,
  };
  vi.stubGlobal(
    "fetch",
    vi
      .fn()
      .mockImplementation(() =>
        Promise.resolve(new Response(JSON.stringify(comparedEnvelope))),
      ),
  );
  await expect(
    requestPanoramaInsight(filters, comparedData, new AbortController().signal),
  ).rejects.toThrow(/incompatível/);
  comparedEnvelope.insight.observation.values[1].value = 150;
  await expect(
    requestPanoramaInsight(filters, comparedData, new AbortController().signal),
  ).resolves.toBeDefined();
  const query = {
    data: result,
    isError: false,
    isPending: false,
    isFetching: false,
    error: null,
  } as unknown as ReturnType<typeof usePanoramaInsight>;
  const view = render(
    <AIInsightCard
      filters={filters}
      data={data}
      query={query}
      onRefreshIndicators={() => {}}
    />,
  );
  expect(
    screen.getByText(/Análise assistida por IA.*fonte de dados interna/),
  ).toBeVisible();
  expect(
    screen.queryByText(/Os números são fictícios/),
  ).not.toBeInTheDocument();
  expect(
    screen.queryByText("Hipótese para investigar"),
  ).not.toBeInTheDocument();
  expect(
    screen.getByText("Mar/2024: comparação indisponível neste recorte"),
  ).toBeVisible();
  await userEvent.click(
    screen.getByRole("button", { name: "Ver análise detalhada" }),
  );
  await userEvent.click(screen.getByRole("button", { name: "Ver fundamento" }));
  const foundation = screen.getByRole("region", {
    name: "Fundamento do insight",
  });
  expect(foundation).toHaveTextContent("Abr/2024 comparado a Mar/2024");
  expect(foundation).toHaveTextContent("Fonte de dados interna");
  expect(screen.getAllByText(/Recife concentra 25%/).length).toBeGreaterThan(0);
  expect(foundation).not.toHaveTextContent(
    /gold.local|Publicação Gold|panorama-sintetico/,
  );

  view.rerender(
    <AIInsightCard
      filters={filters}
      data={data}
      query={{ ...query, isFetching: true }}
      onRefreshIndicators={() => {}}
    />,
  );
  expect(
    screen.queryByText(/Preparando a interpretação da IA/),
  ).not.toBeInTheDocument();
  expect(screen.getAllByText(/Recife concentra 25%/).length).toBeGreaterThan(0);
  view.rerender(
    <AIInsightCard
      filters={filters}
      data={data}
      query={
        {
          ...query,
          isError: true,
          error: new PanoramaInsightApiError("Atualização pendente", true, 503),
        } as ReturnType<typeof usePanoramaInsight>
      }
      onRefreshIndicators={vi.fn()}
    />,
  );
  expect(screen.getAllByText(/Recife concentra 25%/).length).toBeGreaterThan(0);
  expect(
    screen.getByText(/Exibindo a última análise deste recorte/),
  ).toBeInTheDocument();
  for (const status of [403, 409]) {
    view.rerender(
      <AIInsightCard
        filters={filters}
        data={data}
        query={
          {
            ...query,
            isError: true,
            error: new PanoramaInsightApiError(
              "Contexto inválido",
              false,
              status,
              status === 409 ? "invalid_context" : undefined,
            ),
          } as ReturnType<typeof usePanoramaInsight>
        }
        onRefreshIndicators={vi.fn()}
      />,
    );
    expect(screen.queryByText(/Recife concentra 25%/)).not.toBeInTheDocument();
  }
  envelope.insight.observation.values[0].value = (metric.valorAtual ?? 0) + 999;
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(new Response(JSON.stringify(envelope))),
  );
  await expect(
    requestPanoramaInsight(filters, data, new AbortController().signal),
  ).rejects.toThrow(/incompatível/);
});

it("mostra a leitura dos indicadores enquanto a IA ainda prepara a hipótese", () => {
  const filters: PanoramaFilters = {
    periodo: "2024-04",
    comparacao: "anterior",
    municipio: "todos",
    classe: "todas",
  };
  const data = calculateSyntheticPanorama(filters);
  data.origem = {
    kind: "gold",
    isDemo: false,
    version: data.loteVersao,
    contractVersion: "v1",
    fingerprint: "a".repeat(64),
    limitations: [],
  };
  const query = {
    isPending: true,
    isFetching: true,
    isError: false,
    data: undefined,
    error: null,
  } as unknown as ReturnType<typeof usePanoramaInsight>;
  const { rerender } = render(
    <AIInsightCard
      filters={filters}
      data={data}
      query={query}
      onRefreshIndicators={vi.fn()}
    />,
  );
  expect(screen.getByText(/Preparando a interpretação da IA/)).toBeVisible();
  expect(screen.getByText(/de Mar\/2024 para Abr\/2024/)).toBeVisible();
  expect(
    screen.queryByText("Hipótese para investigar"),
  ).not.toBeInTheDocument();
  rerender(
    <AIInsightCard
      filters={filters}
      data={data}
      query={
        {
          ...query,
          isPending: false,
          isFetching: false,
          isError: true,
          error: new PanoramaInsightApiError(
            "Temporariamente indisponível",
            true,
            503,
          ),
        } as ReturnType<typeof usePanoramaInsight>
      }
      onRefreshIndicators={vi.fn()}
    />,
  );
  expect(screen.getByText(/de Mar\/2024 para Abr\/2024/)).toBeVisible();
  expect(
    screen.getByRole("button", { name: "Tentar novamente" }),
  ).toBeVisible();
});

it("encerra a espera da interpretação e permite tentar novamente após o prazo", async () => {
  vi.useFakeTimers();
  try {
    const filters: PanoramaFilters = {
      periodo: "2024-04",
      comparacao: "anterior",
      municipio: "todos",
      classe: "todas",
    };
    vi.stubGlobal(
      "fetch",
      vi.fn(
        (_url, init: RequestInit) =>
          new Promise((_resolve, reject) => {
            init.signal?.addEventListener(
              "abort",
              () => reject(new DOMException("Aborted", "AbortError")),
              { once: true },
            );
          }),
      ),
    );
    const result = requestPanoramaInsight(
      filters,
      calculateSyntheticPanorama(filters),
      new AbortController().signal,
    ).catch((error) => error);
    await vi.advanceTimersByTimeAsync(70_000);
    const error = await result;
    expect(error.status).toBe(504);
    expect(error.retryable).toBe(true);
    expect(error.message).toContain(
      "Os dados do recorte continuam disponíveis",
    );
    expect(vi.getTimerCount()).toBe(0);
  } finally {
    vi.useRealTimers();
  }
});

it("antecipa o texto de concentração e o próximo passo sem aguardar Gemini", () => {
  const filters: PanoramaFilters = {
    periodo: "2026-06",
    comparacao: "anterior",
    municipio: "todos",
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
  data.metricas.receitaFaturada.valorAtual = 100;
  data.metricas.receitaFaturada.valorAnterior = null;
  data.metricas.receitaFaturada.variacaoAbsoluta = null;
  data.metricas.receitaFaturada.variacaoPercentual = null;
  data.distribuicao = {
    dimension: "municipio",
    periodo: "2026-06",
    metricId: data.metricas.receitaFaturada.id,
    unidade: "R$",
    total: 100,
    completo: true,
    pontos: [
      { segmento: "Recife", valor: 70, percentual: 70 },
      { segmento: "Olinda", valor: 30, percentual: 30 },
    ],
    composicaoReceita: {
      dimension: "municipio",
      segmento: "Recife",
      valor: 70,
      participacaoPercentual: 70,
    },
  };
  const query = {
    isPending: true,
    isFetching: true,
    isError: false,
    data: undefined,
    error: null,
  } as unknown as ReturnType<typeof usePanoramaInsight>;
  render(
    <AIInsightCard
      filters={filters}
      data={data}
      query={query}
      onRefreshIndicators={vi.fn()}
    />,
  );
  expect(
    screen.getByText(/Recife concentra 70% da receita observada em Jun\/2026/),
  ).toBeVisible();
  expect(screen.getByText(/explore Recife por classe/)).toBeVisible();
  expect(screen.getByText(/Preparando a interpretação da IA/)).toBeVisible();
  expect(screen.queryByRole("button", { name: "Tentar novamente" })).not.toBeInTheDocument();
});
