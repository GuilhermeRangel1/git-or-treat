import { expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { calculateSyntheticPanorama } from "../../shared/analytics/syntheticData";
import type { PanoramaFilters } from "../../shared/analytics/types";
import AIInsightCard from "./AIInsightCard";
import { requestPanoramaInsight } from "./insightApi";
import type { usePanoramaInsight } from "./usePanoramaInsight";

it("confere os números do KPI e apresenta Gold sem aviso demonstrativo", async () => {
  const filters: PanoramaFilters = {
    periodo: "2024-04",
    comparacao: "nenhuma",
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
        values: [{ label: "Período atual", value: metric.valorAtual }],
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
  render(
    <AIInsightCard
      filters={filters}
      data={data}
      query={query}
      onRefreshIndicators={() => {}}
    />,
  );
  expect(
    screen.getByText(/Análise assistida por IA.*dados Gold/),
  ).toBeVisible();
  expect(
    screen.queryByText(/Os números são fictícios/),
  ).not.toBeInTheDocument();
  expect(screen.getByText("Hipótese para investigar")).toBeVisible();
  envelope.insight.observation.values[0].value = (metric.valorAtual ?? 0) + 999;
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(new Response(JSON.stringify(envelope))),
  );
  await expect(
    requestPanoramaInsight(filters, data, new AbortController().signal),
  ).rejects.toThrow(/incompatível/);
});
