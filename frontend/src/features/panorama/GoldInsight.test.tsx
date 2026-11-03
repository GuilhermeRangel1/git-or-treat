import { expect, it, vi } from "vitest";
import userEvent from "@testing-library/user-event";
import { render, screen } from "@testing-library/react";
import { calculateSyntheticPanorama } from "../../shared/analytics/syntheticData";
import type { PanoramaFilters } from "../../shared/analytics/types";
import AIInsightCard from "./AIInsightCard";
import { requestPanoramaInsight } from "./insightApi";
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
    screen.getByText("Leitura dos valores observados no período"),
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
    screen.getByText(/Recorte alterado · atualizando a interpretação/),
  ).toBeVisible();
  expect(screen.queryByText(/Recife concentra 25%/)).not.toBeInTheDocument();
  expect(
    screen.queryByText(envelope.insight.hypothesis),
  ).not.toBeInTheDocument();
  envelope.insight.observation.values[0].value = (metric.valorAtual ?? 0) + 999;
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(new Response(JSON.stringify(envelope))),
  );
  await expect(
    requestPanoramaInsight(filters, data, new AbortController().signal),
  ).rejects.toThrow(/incompatível/);
});
