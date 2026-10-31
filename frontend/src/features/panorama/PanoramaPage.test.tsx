import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import TestProviders from "../../shared/test/TestProviders";
import PanoramaPage from "./PanoramaPage";
import { calculateSyntheticPanorama } from "../../shared/analytics/syntheticData";
import { resetGoldPublication } from "../../shared/analytics/goldPublication";

function panoramaRequestCount() {
  return vi
    .mocked(fetch)
    .mock.calls.filter(
      ([input]) =>
        new URL(String(input), "http://localhost:5173").pathname ===
        "/api/v1/panorama",
    ).length;
}

function goldMetric(id: string, value: number | null, status: string) {
  return {
    id,
    nome: id,
    categoria: "financeiro",
    tipoGrandeza: "faturado",
    valorAtual: value,
    valorAnterior: null,
    variacaoAbsoluta: null,
    variacaoPercentual: null,
    unidade: "R$",
    definicao: "Definição Gold",
    formula: "Σ(valor)",
    baseZero: false,
    bomSentido: "positivo",
    status,
    limitacoes:
      status === "unavailable" ? ["Não disponível nesta publicação."] : [],
    statusComparacao: "empty",
    limitacoesComparacao: ["Referência ausente."],
  };
}

function goldPanorama(filters: {
  periodo: string;
  comparacao: "anterior" | "ano_anterior" | "nenhuma";
  municipio: string;
  classe: string;
}) {
  const metricas: Record<string, ReturnType<typeof goldMetric>> = {};
  for (const key of [
    "receitaFaturada",
    "receitaPaga",
    "energiaConsumida",
    "energiaFaturada",
    "precoMedioEfetivo",
    "ucsAtivas",
    "continuidadeDec",
    "continuidadeFec",
  ])
    metricas[key] = goldMetric(key, null, "unavailable");
  metricas.receitaFaturada = goldMetric("rec_fat", 0, "available");
  metricas.energiaConsumida = {
    ...goldMetric("ene_con", null, "unavailable"),
    unidade: "kWh",
    categoria: "fisico",
    tipoGrandeza: "consumido",
  };
  metricas.ucsFaturadasNoMes = {
    ...goldMetric("ucs_fat", null, "unavailable"),
    unidade: "UCs",
  };
  const fingerprint = "b".repeat(64);
  return {
    data: {
      filtros: filters,
      periodoIncompleto: false,
      fechamentoMensalDeclarado: false,
      totalRegistros: 1,
      dataAtualizacao: "2026-10-29T10:00:00Z",
      loteVersao: "batch-panorama-ui",
      metricas,
      serieMensal: [
        {
          competencia: filters.periodo,
          label: "Jun/26",
          receitaFaturada: 0,
          receitaPaga: null,
          energiaConsumidaKwh: null,
          energiaFaturadaKwh: null,
          ucsAtivas: null,
          decHoras: null,
          fecVezes: null,
          status: "partial",
        },
      ],
      opcoesFiltros: {
        competencias: ["2026-06", "2026-05"],
        municipios: ["Curitiba"],
        classes: ["Residencial"],
      },
    },
    metadata: {
      contract_version: "2.0.0",
      status: "partial",
      period: {
        start: filters.periodo,
        end: filters.periodo,
        granularity: "month",
      },
      filters: {
        municipio: filters.municipio === "todos" ? null : filters.municipio,
        bairro: null,
        classe: filters.classe === "todas" ? null : filters.classe,
        alimentador: null,
      },
      source: {
        kind: "gold",
        version: "batch-panorama-ui",
        is_demo: false,
        updated_at: "2026-10-29T10:00:00Z",
      },
      limitations: ["Fechamento mensal não declarado."],
      temporal_scope: "monthly",
      schema_version: "gold-csv-v2",
      fingerprint,
    },
  };
}

describe("PanoramaPage (WEB-01)", () => {
  beforeEach(() => {
    localStorage.clear();
    resetGoldPublication();
    vi.stubGlobal(
      "matchMedia",
      vi.fn().mockReturnValue({
        matches: false,
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
      }),
    );
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockImplementation(
          async (input: RequestInfo | URL, init?: RequestInit) => {
            const url = new URL(String(input), "http://localhost:5173");
            if (url.pathname === "/api/v1/ai/insights") {
              const request = JSON.parse(String(init?.body)) as {
                filters: {
                  periodo: string;
                  comparacao: "anterior" | "ano_anterior" | "nenhuma";
                  municipio: string;
                  classe: string;
                };
              };
              const insightData = calculateSyntheticPanorama(request.filters);
              const metric = insightData.metricas.energiaFaturada;
              const [year, month] = request.filters.periodo
                .split("-")
                .map(Number);
              const lastDay = new Date(Date.UTC(year, month, 0)).getUTCDate();
              return new Response(
                JSON.stringify({
                  insight: {
                    contract_version: "v1",
                    correlation_id: "c".repeat(32),
                    audit_reference: null,
                    error: null,
                    status: "answered",
                    context: {
                      metric: metric.nome,
                      unit: metric.unidade,
                      period: {
                        start: `${request.filters.periodo}-01`,
                        end: `${request.filters.periodo}-${String(lastDay).padStart(2, "0")}`,
                        granularity: "month",
                      },
                      filters: request.filters,
                    },
                    observation: {
                      values: [{ label: "Atual", value: metric.valorAtual }],
                    },
                    hypothesis: "Hipótese sintética para teste.",
                    message: null,
                    evidence: [
                      {
                        source: "synthetic.screen",
                        description: "Contexto sintético de teste.",
                        is_demo: true,
                      },
                    ],
                    limitations: ["Sem reconciliação com Gold."],
                  },
                  metric: {
                    id: metric.id,
                    definicao: metric.definicao,
                    formula: metric.formula,
                  },
                  source: {
                    kind: "synthetic",
                    loteVersao: insightData.loteVersao,
                    dataAtualizacao: insightData.dataAtualizacao,
                    isDemo: true,
                    limitacoes: ["Dados sintéticos de teste."],
                  },
                }),
              );
            }
            const params = url.searchParams;
            const data = calculateSyntheticPanorama({
              periodo: params.get("competencia") ?? "2024-04",
              comparacao: params.get("comparacao") as
                "anterior" | "ano_anterior" | "nenhuma",
              municipio: params.get("municipio")!,
              classe: params.get("classe")!,
            });
            return new Response(JSON.stringify({ data }));
          },
        ),
    );
  });

  it("resolve deep link Gold fora do catÃ¡logo sintÃ©tico e apresenta opÃ§Ãµes, nulos e insight indisponÃ­vel", async () => {
    const requests: URL[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url = new URL(String(input), "http://localhost:5173");
        requests.push(url);
        if (url.pathname === "/api/v1/panorama") {
          const params = url.searchParams;
          return new Response(
            JSON.stringify(
              goldPanorama({
                periodo: params.get("competencia") ?? "2026-06",
                comparacao: (params.get("comparacao") ?? "anterior") as
                  "anterior" | "ano_anterior" | "nenhuma",
                municipio: params.get("municipio") ?? "todos",
                classe: params.get("classe") ?? "todas",
              }),
            ),
          );
        }
        return new Response("{}", { status: 500 });
      }),
    );

    render(
      <TestProviders>
        <MemoryRouter
          initialEntries={["/panorama?municipio=Curitiba&classe=Residencial"]}
        >
          <PanoramaPage />
        </MemoryRouter>
      </TestProviders>,
    );

    await waitFor(() =>
      expect(
        screen.getByText(
          "Insights automáticos não estão disponíveis para esta fonte.",
        ),
      ).toBeVisible(),
    );
    expect(
      await screen.findByRole("article", { name: /Valor faturado/ }),
    ).toBeVisible();
    expect(screen.getAllByText("Indisponível").length).toBeGreaterThan(0);
    expect(requests.some((url) => url.pathname === "/api/v1/ai/insights")).toBe(
      false,
    );
    expect(
      requests.some(
        (url) =>
          url.searchParams.get("municipio") === "todos" &&
          url.searchParams.get("classe") === "todas",
      ),
      requests.map((url) => url.toString()).join("\n"),
    ).toBe(true);
    await waitFor(() =>
      expect(
        requests.some(
          (url) =>
            url.searchParams.get("municipio") === "Curitiba" &&
            url.searchParams.get("classe") === "Residencial" &&
            url.searchParams.get("competencia") === "2026-06",
        ),
        requests.map((url) => url.toString()).join("\n"),
      ).toBe(true),
    );

    await userEvent.click(
      screen.getByRole("button", { name: "Ajustar filtros" }),
    );
    const dialog = screen.getByRole("dialog", { name: "Ajustar filtros" });
    expect(
      within(dialog).getByRole("option", { name: "Curitiba" }),
    ).toBeInTheDocument();
    expect(
      within(dialog).getByRole("option", { name: "Residencial" }),
    ).toBeInTheDocument();
    expect(
      within(dialog).getByRole("option", { name: "Jun/2026" }),
    ).toBeInTheDocument();
  });

  it("não mostra o agregado global da descoberta como se fosse o recorte do deep link", async () => {
    const requests: URL[] = [];
    let signalTargetStarted!: () => void;
    const pendingTargets: {
      url: URL;
      resolve: (response: Response) => void;
    }[] = [];
    const targetStarted = new Promise<void>((resolve) => {
      signalTargetStarted = resolve;
    });
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url = new URL(String(input), "http://localhost:5173");
        requests.push(url);
        if (url.pathname !== "/api/v1/panorama")
          return new Response("{}", { status: 500 });
        if (url.searchParams.get("municipio") === "Curitiba") {
          signalTargetStarted();
          return new Promise<Response>((resolve) => {
            pendingTargets.push({ url, resolve });
          });
        }
        const global = goldPanorama({
          periodo: "2026-06",
          comparacao: "anterior",
          municipio: "todos",
          classe: "todas",
        });
        global.data.metricas.receitaFaturada.valorAtual = 987654;
        return new Response(JSON.stringify(global));
      }),
    );

    render(
      <TestProviders>
        <MemoryRouter
          initialEntries={["/panorama?municipio=Curitiba&classe=Residencial"]}
        >
          <PanoramaPage />
        </MemoryRouter>
      </TestProviders>,
    );

    await targetStarted;
    expect(
      screen.queryByRole("region", {
        name: "Indicadores principais do Panorama",
      }),
    ).not.toBeInTheDocument();
    expect(screen.queryByText(/987,7 mil/)).not.toBeInTheDocument();
    expect(
      requests.some(
        (url) =>
          url.searchParams.get("municipio") === "todos" &&
          url.searchParams.get("classe") === "todas",
      ),
    ).toBe(true);

    await waitFor(() =>
      expect(
        requests.some(
          (url) =>
            url.searchParams.get("municipio") === "Curitiba" &&
            url.searchParams.get("competencia") === "2026-06",
        ),
      ).toBe(true),
    );
    for (const target of pendingTargets) {
      const params = target.url.searchParams;
      target.resolve(
        new Response(
          JSON.stringify(
            goldPanorama({
              periodo: params.get("competencia") ?? "2026-06",
              comparacao: (params.get("comparacao") ?? "anterior") as
                "anterior" | "ano_anterior" | "nenhuma",
              municipio: params.get("municipio") ?? "todos",
              classe: params.get("classe") ?? "todas",
            }),
          ),
        ),
      );
    }
    await waitFor(() =>
      expect(
        screen.queryByText("Erro na consulta dos indicadores"),
        requests.map((url) => url.toString()).join("\n"),
      ).not.toBeInTheDocument(),
    );
    expect(
      await screen.findByRole("article", { name: /Valor faturado/ }),
    ).toBeVisible();
    expect(screen.queryByText(/987,7 mil/)).not.toBeInTheDocument();
  });

  it.each([
    "comparacao=bad",
    "periodo=2024-13",
    "municipio=Natal",
    "classe=bad",
    "periodo=",
    "comparacao=anterior&comparacao=nenhuma",
  ])(
    "bloqueia consulta com URL inválida: %s e permite restaurar",
    async (query) => {
      render(
        <TestProviders>
          <MemoryRouter initialEntries={[`/panorama?${query}`]}>
            <PanoramaPage />
          </MemoryRouter>
        </TestProviders>,
      );
      expect(await screen.findByText("Filtros inválidos na URL")).toBeVisible();
      const needsSourceDiscovery =
        query.includes("municipio=") || query.includes("classe=");
      expect(panoramaRequestCount()).toBe(needsSourceDiscovery ? 1 : 0);
      await userEvent.click(
        screen.getByRole("button", { name: "Restaurar filtros padrão" }),
      );
      expect(await screen.findByText(/R\$ 76,5 mil/)).toBeVisible();
      expect(panoramaRequestCount()).toBe(needsSourceDiscovery ? 2 : 1);
    },
  );

  it("mantém valores parciais e separa a hierarquia dos KPIs", async () => {
    render(
      <TestProviders>
        <MemoryRouter initialEntries={["/panorama?periodo=2024-05"]}>
          <PanoramaPage />
        </MemoryRouter>
      </TestProviders>,
    );
    expect(await screen.findByText(/R\$ 31 mil/)).toBeVisible();
    expect(screen.queryByText("-59,48%")).not.toBeInTheDocument();
    const main = screen.getByRole("region", {
      name: "Indicadores principais do Panorama",
    });
    expect(within(main).getAllByRole("article")).toHaveLength(4);
    expect(
      screen.queryByText("Indicadores complementares"),
    ).not.toBeInTheDocument();
  });

  it("mostra falha da API sem substituir por números locais e permite tentar novamente", async () => {
    vi.mocked(fetch).mockRejectedValueOnce(new Error("offline"));
    render(
      <TestProviders>
        <MemoryRouter>
          <PanoramaPage />
        </MemoryRouter>
      </TestProviders>,
    );
    expect(
      await screen.findByText("Erro na consulta dos indicadores"),
    ).toBeVisible();
    expect(screen.queryByText(/R\$ 76,5 mil/)).not.toBeInTheDocument();
    await userEvent.click(
      screen.getByRole("button", { name: /Tentar novamente/i }),
    );
    expect(await screen.findByText(/R\$ 76,5 mil/)).toBeVisible();
  });

  it("mantém o último conjunto válido quando uma atualização falha", async () => {
    const fallback = vi.mocked(fetch).getMockImplementation();
    expect(fallback).toBeTypeOf("function");
    if (!fallback) return;
    let failNextPanorama = false;
    vi.mocked(fetch).mockImplementation(async (input, init) => {
      const url = new URL(String(input), "http://localhost:5173");
      if (failNextPanorama && url.pathname === "/api/v1/panorama") {
        failNextPanorama = false;
        throw new Error("offline");
      }
      return fallback(input, init);
    });
    render(
      <TestProviders>
        <MemoryRouter>
          <PanoramaPage />
        </MemoryRouter>
      </TestProviders>,
    );
    expect(await screen.findByText(/R\$ 76,5 mil/)).toBeVisible();
    failNextPanorama = true;
    await userEvent.click(
      screen.getByRole("button", { name: "Ver estado de atualização" }),
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Atualizar indicadores" }),
    );
    expect(
      await screen.findByText(
        "Atualização pendente · exibindo o último conjunto válido.",
      ),
    ).toBeVisible();
    expect(screen.getByText(/R\$ 76,5 mil/)).toBeVisible();
    expect(
      screen.getByRole("button", { name: /Tentar atualizar novamente/ }),
    ).toBeVisible();
  });

  it("trata comparação nula sem mensagens repetidas nos cartões", async () => {
    const data = calculateSyntheticPanorama({
      periodo: "2024-04",
      comparacao: "nenhuma",
      municipio: "todos",
      classe: "todas",
    });
    for (const metric of Object.values(data.metricas)) {
      metric.valorAnterior = null;
      metric.variacaoPercentual = null;
      metric.variacaoAbsoluta = null;
    }
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify({ data })),
    );
    render(
      <TestProviders>
        <MemoryRouter initialEntries={["/panorama?comparacao=nenhuma"]}>
          <PanoramaPage />
        </MemoryRouter>
      </TestProviders>,
    );
    expect(await screen.findByText(/R\$ 76,5 mil/)).toBeVisible();
    const main = screen.getByRole("region", {
      name: "Indicadores principais do Panorama",
    });
    expect(within(main).queryByText("Sem comparação")).not.toBeInTheDocument();
  });

  it("rejeita resposta incompleta da API", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify({ data: { metricas: {} } })),
    );
    render(
      <TestProviders>
        <MemoryRouter>
          <PanoramaPage />
        </MemoryRouter>
      </TestProviders>,
    );
    expect(
      await screen.findByText("Erro na consulta dos indicadores"),
    ).toBeVisible();
  });

  it("renderiza o cabeçalho e os indicadores com os números da base sintética (benchmark)", async () => {
    render(
      <TestProviders>
        <MemoryRouter initialEntries={["/panorama"]}>
          <PanoramaPage />
        </MemoryRouter>
      </TestProviders>,
    );

    // Título e subtítulo preservados
    expect(
      screen.getByRole("heading", {
        level: 1,
        name: "Sua rede, em perspectiva.",
      }),
    ).toBeVisible();

    // Aguarda o carregamento dos dados e verifica os valores do benchmark (PRD WEB-01)
    expect(await screen.findByText(/R\$ 76,5 mil/)).toBeVisible();
    expect(screen.getByText("90 MWh")).toBeVisible();
    expect(screen.getByText("1.248 UCs")).toBeVisible();
    expect(screen.getByText("Valor faturado")).toBeVisible();
    expect(screen.getByText("Consumo apurado")).toBeVisible();
    expect(screen.getByText("Base de UCs")).toBeVisible();
    expect(screen.getByText("UCs faturadas no mês")).toBeVisible();
    expect(screen.getAllByRole("article")).toHaveLength(4);
    await userEvent.click(
      screen.getByRole("button", { name: "Ver fundamentos" }),
    );
    const foundations = screen.getByRole("dialog", {
      name: "Fundamentos do Panorama",
    });
    expect(
      within(foundations).getByText("Indicadores principais"),
    ).toBeVisible();
    expect(within(foundations).getByText(/Preço observado/)).toBeVisible();
    expect(within(foundations).getByText(/^FEC/)).toBeVisible();
  });

  it("alterar o filtro de município modifica os dados exibidos", async () => {
    const user = userEvent.setup();
    render(
      <TestProviders>
        <MemoryRouter initialEntries={["/panorama"]}>
          <PanoramaPage />
        </MemoryRouter>
      </TestProviders>,
    );

    // Aguarda carga inicial
    expect(await screen.findByText(/R\$ 76,5 mil/)).toBeVisible();

    await user.click(screen.getByRole("button", { name: "Ajustar filtros" }));
    const municipioSelect = screen.getByLabelText("Município");
    await user.selectOptions(municipioSelect, "Recife");
    expect(screen.getByText(/R\$ 76,5 mil/)).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Aplicar filtros" }));
    // Recife soma R$ 38 mil e 620 UCs
    expect(await screen.findByText(/R\$ 38 mil/)).toBeVisible();
    expect(screen.getByText(/620 UCs/)).toBeVisible();
  });

  it("exibe aviso de período incompleto na competência 2024-05", async () => {
    render(
      <TestProviders>
        <MemoryRouter initialEntries={["/panorama?periodo=2024-05"]}>
          <PanoramaPage />
        </MemoryRouter>
      </TestProviders>,
    );

    expect(
      await screen.findByText(/Competência Mai\/2024 · dados preliminares/i),
    ).toBeVisible();
  });

  it("exibe estado vazio legítimo quando recorte não possui registros", async () => {
    render(
      <TestProviders>
        <MemoryRouter initialEntries={["/panorama?classe=Rural"]}>
          <PanoramaPage />
        </MemoryRouter>
      </TestProviders>,
    );

    expect(
      await screen.findByText("Nenhum registro para o recorte selecionado"),
    ).toBeVisible();
    expect(
      screen.getByRole("button", { name: "Restaurar filtros padrão" }),
    ).toBeVisible();
  });

  it("permite abrir a definição e fórmula de uma métrica", async () => {
    const user = userEvent.setup();
    render(
      <TestProviders>
        <MemoryRouter initialEntries={["/panorama"]}>
          <PanoramaPage />
        </MemoryRouter>
      </TestProviders>,
    );

    // Aguarda carga
    await screen.findByText(/R\$ 76,5 mil/);

    await userEvent.click(
      screen.getByRole("button", { name: "Ver fundamentos" }),
    );

    const dialog = screen.getByRole("dialog", {
      name: "Fundamentos do Panorama",
    });
    await user.click(
      within(dialog).getAllByText("Definição e fórmula", {
        selector: "summary",
      })[0],
    );

    expect(
      within(dialog).getByText(
        "Total monetário faturado no ciclo de faturamento da competência.",
      ),
    ).toBeVisible();
    expect(
      within(dialog).getByText("Σ(faturas_emitidas.valor_total)"),
    ).toBeVisible();
  });

  it("alterna entre visualização gráfica e tabela na série histórica", async () => {
    const user = userEvent.setup();
    render(
      <TestProviders>
        <MemoryRouter initialEntries={["/panorama"]}>
          <PanoramaPage />
        </MemoryRouter>
      </TestProviders>,
    );

    // Aguarda carga
    await screen.findByText(/R\$ 76,5 mil/);

    const showData = screen.getByRole("button", {
      name: /Ver tabela da série/,
    });
    await user.click(showData);
    expect(screen.getByRole("table")).toBeVisible();
    expect(
      screen.getByRole("dialog", { name: "Tabela da série" }),
    ).toBeVisible();
  });
});
