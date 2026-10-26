import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { createQueryClient } from "../../shared/api/query-client";
import { calculateSyntheticPanorama } from "../../shared/analytics/syntheticData";
import type { PanoramaFilters } from "../../shared/analytics/types";
import TestProviders from "../../shared/test/TestProviders";
import { ThemeProvider } from "../../shared/theme/ThemeProvider";
import PanoramaPage from "./PanoramaPage";

function dateRange(period: string) {
  const [year, month] = period.split("-").map(Number);
  return {
    start: `${period}-01`,
    end: `${period}-${String(new Date(Date.UTC(year, month, 0)).getUTCDate()).padStart(2, "0")}`,
    granularity: "month",
  };
}

function successEnvelope(filters: PanoramaFilters) {
  const data = calculateSyntheticPanorama(filters);
  const metric = data.metricas.energiaFaturada;
  const delta = metric.variacaoAbsoluta ?? 0;
  const direction =
    metric.valorAnterior == null
      ? "indisponivel"
      : delta < 0
        ? "queda"
        : delta > 0
          ? "alta"
          : "estavel";
  const observations = [{ label: "Período atual", value: metric.valorAtual }];
  if (metric.valorAnterior != null) {
    observations.push({
      label: "Período comparado",
      value: metric.valorAnterior,
    });
  }

  return {
    insight: {
      contract_version: "v1",
      correlation_id: "a".repeat(32),
      audit_reference: null,
      error: null,
      status: "answered",
      context: {
        metric: metric.nome,
        unit: metric.unidade,
        period: dateRange(filters.periodo),
        filters,
      },
      observation: { values: observations },
      hypothesis:
        "Investigue a composição deste recorte sem atribuir uma causa.",
      message: null,
      evidence: [
        {
          source: "synthetic.screen",
          description: "Contexto do recorte sintético.",
          is_demo: true,
        },
      ],
      limitations: ["A hipótese não comprova causa; base sintética sem Gold."],
    },
    metric: {
      id: metric.id,
      definicao: metric.definicao,
      formula: metric.formula,
    },
    source: {
      kind: "synthetic",
      loteVersao: data.loteVersao,
      dataAtualizacao: data.dataAtualizacao,
      isDemo: true,
      limitacoes: [
        "Os números são fictícios e servem apenas para demonstração; não representam dados operacionais reais.",
      ],
    },
    analysis: {
      direcao: direction,
      variacaoPercentual: metric.variacaoPercentual,
      principalContribuicao:
        filters.municipio === "todos" && filters.classe === "todas"
          ? {
              dimension: "municipio",
              segmento: "Recife",
              variacaoAbsoluta: -5000,
              participacaoPercentual: 50,
            }
          : filters.municipio === "Olinda" && filters.classe === "todas"
            ? {
                dimension: "classe",
                segmento: "Residencial",
                variacaoAbsoluta: -2500,
                participacaoPercentual: 83.3,
              }
            : null,
      compensacao: null,
    },
  };
}

function panoramaResponse(filters: PanoramaFilters) {
  return new Response(
    JSON.stringify({ data: calculateSyntheticPanorama(filters) }),
  );
}

function renderPanorama(initialEntry = "/panorama") {
  return render(
    <TestProviders>
      <MemoryRouter initialEntries={[initialEntry]}>
        <PanoramaPage />
      </MemoryRouter>
    </TestProviders>,
  );
}

function renderPanoramaWithQueryClient(initialEntry = "/panorama") {
  const queryClient = createQueryClient();
  const result = render(
    <QueryClientProvider client={queryClient}>
      <ThemeProvider>
        <MemoryRouter initialEntries={[initialEntry]}>
          <PanoramaPage />
        </MemoryRouter>
      </ThemeProvider>
    </QueryClientProvider>,
  );
  return { ...result, queryClient };
}

describe("IA-04 contextual insight on Panorama", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.stubGlobal(
      "matchMedia",
      vi.fn().mockReturnValue({
        matches: false,
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
      }),
    );
  });

  it("shows the calculated reading separately from measured values and exposes the foundation", async () => {
    const fetchMock = vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = new URL(String(input), "http://localhost:5173");
        if (url.pathname === "/api/v1/panorama") {
          const filters: PanoramaFilters = {
            periodo: url.searchParams.get("competencia")!,
            comparacao: url.searchParams.get(
              "comparacao",
            ) as PanoramaFilters["comparacao"],
            municipio: url.searchParams.get("municipio")!,
            classe: url.searchParams.get("classe")!,
          };
          return panoramaResponse(filters);
        }

        const request = JSON.parse(String(init?.body)) as {
          filters: PanoramaFilters;
        };
        return new Response(JSON.stringify(successEnvelope(request.filters)));
      },
    );
    vi.stubGlobal("fetch", fetchMock);

    renderPanorama();

    const insight = await screen.findByRole("region", {
      name: "Insight contextual do Panorama",
    });
    expect(
      within(insight).getByText("Dado observado no Panorama"),
    ).toBeVisible();
    expect(within(insight).getByText("Leitura do recorte")).toBeVisible();
    expect(
      await within(insight).findByText(/caiu 10% de Mar\/2024 para Abr\/2024/),
    ).toBeVisible();
    expect(within(insight).getByText("Hipótese para investigar")).toBeVisible();
    expect(
      within(insight).getByText(
        "Investigue a composição deste recorte sem atribuir uma causa.",
      ),
    ).toBeVisible();
    expect(
      within(insight).getByText(
        "Sugestão de investigação; não comprova causa.",
      ),
    ).toBeVisible();
    expect(
      within(insight).getByText(/Principal movimento: Recife/),
    ).toBeVisible();
    expect(
      within(insight).getByText(/Próximo passo:/).parentElement,
    ).toHaveTextContent("Próximo passo: explore Recife por classe.");
    expect(
      within(insight).queryByText(/compensou parte/),
    ).not.toBeInTheDocument();
    expect(
      within(insight).queryByText(/Município: Todos/),
    ).not.toBeInTheDocument();
    const detailButton = within(insight).getByRole("button", {
      name: "Ver análise detalhada",
    });
    expect(detailButton).toBeVisible();
    expect(detailButton).toHaveClass("text-[var(--accent-goiaba-text)]");
    expect(detailButton).not.toHaveClass("text-white");
    expect(
      screen.getByRole("region", {
        name: "Indicadores principais do Panorama",
      }),
    ).toBeVisible();
    expect(insight.parentElement).toHaveClass(
      "items-start",
      "xl:items-stretch",
    );
    expect(insight.parentElement).toHaveClass(
      "xl:grid-cols-[minmax(0,1fr)_340px]",
    );

    await userEvent.click(
      within(insight).getByRole("button", { name: "Ver análise detalhada" }),
    );
    const drawer = screen.getByRole("dialog", {
      name: "Insight",
    });
    expect(
      within(drawer).getByRole("heading", {
        name: "Hipótese para investigar",
      }),
    ).toBeVisible();
    expect(
      within(drawer).getByText(
        "Investigue a composição deste recorte sem atribuir uma causa.",
      ),
    ).toBeVisible();
    expect(drawer).toHaveStyle({
      position: "fixed",
      top: "0px",
      right: "0px",
      bottom: "0px",
      left: "auto",
    });
    expect(within(drawer).getByText(/Período: Abr\/2024/)).toBeVisible();
    expect(
      within(drawer).getByRole("heading", { name: "Recomendação" }),
    ).toBeVisible();
    expect(
      within(drawer).getByRole("button", {
        name: "Fechar análise detalhada",
      }),
    ).toBeVisible();
    expect(within(drawer).getByText(/Município: Todos/)).toBeVisible();
    await userEvent.click(
      within(drawer).getByRole("button", { name: "Ver fundamento" }),
    );
    const foundation = within(drawer).getByRole("region", {
      name: "Fundamento do insight",
    });
    expect(foundation).toHaveAttribute("tabindex", "0");
    expect(within(foundation).getByText("Fórmula aplicada")).toBeVisible();
    expect(foundation).toHaveTextContent(
      "Dados sintéticos · panorama-sintetico-2024.04-v1",
    );
    expect(foundation).not.toHaveTextContent("Lote Gold");
    expect(
      within(drawer).getAllByText(
        "Os números são fictícios e servem apenas para demonstração; não representam dados operacionais reais.",
      ).length,
    ).toBeGreaterThan(0);
    expect(within(drawer).queryByText(/PRD|WEB-01/)).not.toBeInTheDocument();
    fireEvent(drawer, new Event("cancel", { bubbles: true, cancelable: true }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(
      within(insight).getByRole("button", { name: "Ver análise detalhada" }),
    ).toHaveFocus();

    const request = fetchMock.mock.calls.find(([input]) =>
      String(input).includes("/api/v1/ai/insights"),
    );
    expect(request).toBeDefined();
    const body = JSON.parse(String(request?.[1]?.body));
    expect(body.filters).toEqual({
      periodo: "2024-04",
      comparacao: "anterior",
      municipio: "todos",
      classe: "todas",
    });
    expect(body.loteVersao).toBe("panorama-sintetico-2024.04-v1");
    expect(body.observations).toBeUndefined();
  });

  it("hides a cached insight and shows the stale-batch warning after a 409", async () => {
    let insightRequests = 0;
    const fetchMock = vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = new URL(String(input), "http://localhost:5173");
        if (url.pathname === "/api/v1/panorama") {
          const filters: PanoramaFilters = {
            periodo: url.searchParams.get("competencia")!,
            comparacao: url.searchParams.get(
              "comparacao",
            ) as PanoramaFilters["comparacao"],
            municipio: url.searchParams.get("municipio")!,
            classe: url.searchParams.get("classe")!,
          };
          return panoramaResponse(filters);
        }

        insightRequests += 1;
        if (insightRequests === 1) {
          const request = JSON.parse(String(init?.body)) as {
            filters: PanoramaFilters;
          };
          return new Response(JSON.stringify(successEnvelope(request.filters)));
        }
        return new Response(
          JSON.stringify({
            contract_version: "v1",
            status: "error",
            correlation_id: "b".repeat(32),
            message: "O lote mudou desde que os indicadores foram carregados.",
            error: { code: "invalid_context", retryable: false },
          }),
          { status: 409 },
        );
      },
    );
    vi.stubGlobal("fetch", fetchMock);

    const { queryClient } = renderPanoramaWithQueryClient();
    const insight = await screen.findByRole("region", {
      name: "Insight contextual do Panorama",
    });
    expect(
      await within(insight).findByText(/caiu 10% de Mar\/2024 para Abr\/2024/),
    ).toBeVisible();
    await userEvent.click(
      within(insight).getByRole("button", { name: "Ver análise detalhada" }),
    );
    const drawer = screen.getByRole("dialog", { name: "Insight" });

    await act(async () => {
      await queryClient.invalidateQueries({
        queryKey: ["panorama-insight"],
      });
    });

    const staleWarning =
      "O lote mudou desde que os indicadores foram carregados. Atualize o Panorama para sincronizar o contexto.";
    await waitFor(() => {
      const cardWarning = within(insight)
        .getAllByRole("status")
        .find((status) => !drawer.contains(status));
      expect(cardWarning).toHaveTextContent(staleWarning);
    });
    expect(within(drawer).getByRole("status")).toHaveTextContent(staleWarning);
    expect(
      within(insight).queryByText(/caiu 10% de Mar\/2024 para Abr\/2024/),
    ).not.toBeInTheDocument();
    expect(
      within(drawer).queryByText(/caiu 10% de Mar\/2024 para Abr\/2024/),
    ).not.toBeInTheDocument();
    expect(
      within(insight).queryByText(
        "Investigue a composição deste recorte sem atribuir uma causa.",
      ),
    ).not.toBeInTheDocument();
    expect(
      within(drawer).queryByText(
        "Investigue a composição deste recorte sem atribuir uma causa.",
      ),
    ).not.toBeInTheDocument();
    expect(
      screen.getByRole("region", {
        name: "Indicadores principais do Panorama",
      }),
    ).toBeVisible();
  });

  it("keeps indicators visible if insight service fails", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url = new URL(String(input), "http://localhost:5173");
        if (url.pathname === "/api/v1/panorama")
          return panoramaResponse({
            periodo: url.searchParams.get("competencia")!,
            comparacao: url.searchParams.get(
              "comparacao",
            ) as PanoramaFilters["comparacao"],
            municipio: url.searchParams.get("municipio")!,
            classe: url.searchParams.get("classe")!,
          });
        return new Response(
          JSON.stringify({
            contract_version: "v1",
            status: "error",
            correlation_id: "b".repeat(32),
            message: "Serviço de insight indisponível.",
            error: { code: "service_unavailable", retryable: true },
          }),
          { status: 503 },
        );
      }),
    );

    renderPanorama();

    expect(
      await screen.findByText("O insight não está disponível agora."),
    ).toBeVisible();
    expect(
      screen.getByRole("region", {
        name: "Indicadores principais do Panorama",
      }),
    ).toBeVisible();
    expect(
      screen.getByRole("button", { name: "Tentar novamente" }),
    ).toBeVisible();
  });

  it("does not let an older filter response replace the current insight", async () => {
    let resolveOldInsight: ((response: Response) => void) | undefined;
    let oldInsightStarted = false;
    const fetchMock = vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = new URL(String(input), "http://localhost:5173");
        if (url.pathname === "/api/v1/panorama") {
          const filters: PanoramaFilters = {
            periodo: url.searchParams.get("competencia")!,
            comparacao: url.searchParams.get(
              "comparacao",
            ) as PanoramaFilters["comparacao"],
            municipio: url.searchParams.get("municipio")!,
            classe: url.searchParams.get("classe")!,
          };
          return panoramaResponse(filters);
        }
        const request = JSON.parse(String(init?.body)) as {
          filters: PanoramaFilters;
        };
        if (request.filters.municipio === "todos") {
          oldInsightStarted = true;
          return new Promise<Response>((resolve) => {
            resolveOldInsight = resolve;
          });
        }
        return new Response(JSON.stringify(successEnvelope(request.filters)));
      },
    );
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    renderPanorama();
    await waitFor(() => expect(oldInsightStarted).toBe(true));

    await user.click(screen.getByRole("button", { name: "Ajustar filtros" }));
    await user.selectOptions(screen.getByLabelText("Município"), "Recife");
    await user.click(screen.getByRole("button", { name: "Aplicar filtros" }));
    expect(
      await screen.findByText(
        /Energia Faturada caiu .* de Mar\/2024 para Abr\/2024/,
      ),
    ).toBeVisible();
    expect(
      screen.queryByText(/Principal movimento: Recife/),
    ).not.toBeInTheDocument();

    await act(async () => {
      resolveOldInsight?.(
        new Response(
          JSON.stringify(
            successEnvelope({
              periodo: "2024-04",
              comparacao: "anterior",
              municipio: "todos",
              classe: "todas",
            }),
          ),
        ),
      );
    });
    expect(
      screen.getByText(/Energia Faturada caiu .* de Mar\/2024 para Abr\/2024/),
    ).toBeVisible();
    expect(
      screen.queryByText(/Principal movimento: Recife/),
    ).not.toBeInTheDocument();
  });
});
