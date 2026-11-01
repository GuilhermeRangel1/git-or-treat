import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import {
  MemoryRouter,
  useLocation,
  useNavigate,
  useSearchParams,
} from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import ReceitaPage from "./ReceitaPage";
import RevenueBreakdown from "./RevenueBreakdown";
import RevenueSeries from "./RevenueSeries";
import type { RevenueEnvelope } from "./contract";
import { revenueRefinementDestination } from "./revenue-filters";

const response = {
  data: {
    currency_unit: "BRL",
    energy_unit: "kWh",
    total_billed_amount: 156500,
    total_paid_amount: 154000,
    total_measured_energy_kwh: 193000,
    total_billed_energy_kwh: 190000,
    observed_price_brl_per_kwh: 0.8237,
    series: [
      {
        competencia: "2025-01",
        billed_amount: 80000,
        paid_amount: 79000,
        measured_energy_kwh: 101000,
        billed_energy_kwh: 100000,
      },
      {
        competencia: "2025-02",
        billed_amount: 76500,
        paid_amount: 75000,
        measured_energy_kwh: 92000,
        billed_energy_kwh: 90000,
      },
    ],
    comparison: {
      initial: {
        competencia: "2025-01",
        billed_amount: 80000,
        billed_energy_kwh: 100000,
        observed_price_brl_per_kwh: 0.8,
        billed_uc_count: 20,
        status: "available",
        limitations: [],
      },
      final: {
        competencia: "2025-02",
        billed_amount: 76500,
        billed_energy_kwh: 90000,
        observed_price_brl_per_kwh: 0.85,
        billed_uc_count: 20,
        status: "available",
        limitations: [],
      },
      billed_amount_change_brl: -3500,
      billed_energy_change_kwh: -10000,
      measured_energy_change_kwh: -9000,
      billed_amount_change_percent: -4.38,
    },
    price_volume: {
      method: "endpoint_price_volume",
      reference_version: "dev03-v1",
      price_effect_brl: 5000,
      volume_effect_brl: -8000,
      interaction_effect_brl: -500,
      rounding_adjustment_brl: 0,
      status: "available",
      limitations: [],
    },
    coverage: {
      requested_months: ["2025-01", "2025-02"],
      billed_amount: {
        status: "available",
        covered_months: ["2025-01", "2025-02"],
        missing_months: [],
        limitations: [],
      },
      billed_energy_kwh: {
        status: "available",
        covered_months: ["2025-01", "2025-02"],
        missing_months: [],
        limitations: [],
      },
      paid_amount: {
        status: "partial",
        covered_months: ["2025-01"],
        missing_months: ["2025-02"],
        limitations: ["Pagamento ainda não coberto em fevereiro."],
      },
      measured_energy_kwh: {
        status: "available",
        covered_months: ["2025-01", "2025-02"],
        missing_months: [],
        limitations: [],
      },
    },
    quality: {
      small_base_threshold_uc: 5,
      small_base: false,
      percent_change_eligible: true,
      limitations: [],
    },
    breakdown: {
      dimension: "municipio",
      items: [
        {
          key: "municipio:Olinda",
          label: "Olinda",
          filters: {
            municipio: "Olinda",
            bairro: null,
            classe: null,
            alimentador: null,
          },
          comparison: {
            initial: {
              competencia: "2025-01",
              billed_amount: 40000,
              billed_energy_kwh: 50000,
              observed_price_brl_per_kwh: 0.8,
              billed_uc_count: 10,
              status: "available",
              limitations: [],
            },
            final: {
              competencia: "2025-02",
              billed_amount: 38000,
              billed_energy_kwh: 45000,
              observed_price_brl_per_kwh: 0.8444,
              billed_uc_count: 10,
              status: "available",
              limitations: [],
            },
            billed_amount_change_brl: -2000,
            billed_energy_change_kwh: -5000,
            measured_energy_change_kwh: -4500,
            billed_amount_change_percent: -5,
          },
          quality: {
            small_base_threshold_uc: 5,
            small_base: false,
            percent_change_eligible: true,
            limitations: [],
          },
        },
      ],
      reconciliation: {
        status: "unavailable",
        initial_known_sum_brl: 40000,
        final_known_sum_brl: 38000,
        comparable_change_sum_brl: -2000,
        non_comparable_group_count: 0,
        unattributed_change_brl: 0,
        residual_brl: -1500,
        limitations: ["A amostra de teste contém apenas um município."],
      },
    },
    filter_options: {
      municipios: ["Olinda", "Recife"],
      bairros: [
        { municipio: "Olinda", bairro: "Bairro Novo" },
        { municipio: "Recife", bairro: "Bairro Novo" },
      ],
      classes: ["Comercial", "Residencial"],
    },
  },
  metadata: {
    contract_version: "1.1.0",
    status: "partial",
    period: { start: "2025-01", end: "2025-02", granularity: "month" },
    filters: {
      municipio: null,
      bairro: null,
      classe: null,
      alimentador: null,
    },
    source: {
      kind: "synthetic",
      version: "dev03-v1",
      is_demo: true,
      updated_at: "2025-02-28T00:00:00Z",
    },
    limitations: ["Valor pago está parcial."],
  },
};

it("oculta colunas inteiramente ausentes e volta a mostrá-las para zero observado", () => {
  const data = structuredClone(response);
  data.data.series.forEach((row) => {
    (row as { paid_amount: number | null }).paid_amount = null;
    (row as { billed_energy_kwh: number | null }).billed_energy_kwh = null;
  });
  const { rerender } = render(
    <RevenueSeries envelope={data as unknown as RevenueEnvelope} />,
  );
  expect(
    screen.queryByRole("columnheader", { name: "Receita paga (BRL)" }),
  ).not.toBeInTheDocument();
  expect(
    screen.queryByRole("columnheader", { name: "Energia faturada (kWh)" }),
  ).not.toBeInTheDocument();
  expect(
    screen.getByText(/Energia faturada não está disponível/),
  ).toBeVisible();
  data.data.series[0].paid_amount = 0;
  data.data.series[0].billed_energy_kwh = 0;
  rerender(<RevenueSeries envelope={data as unknown as RevenueEnvelope} />);
  expect(
    screen.getByRole("columnheader", { name: "Receita paga (BRL)" }),
  ).toBeVisible();
  expect(
    screen.getByRole("columnheader", { name: "Energia faturada (kWh)" }),
  ).toBeVisible();
});

it("pagina muitos recortes e mantém a soma de todos os grupos", async () => {
  const data = structuredClone(response);
  data.data.breakdown.items = Array.from({ length: 25 }, (_, index) => ({
    ...data.data.breakdown.items[0],
    key: `grupo-${index}`,
    label: `Grupo ${index}`,
    filters: {
      ...data.data.breakdown.items[0].filters,
      municipio: `Grupo ${index}`,
    },
  }));
  render(
    <RevenueBreakdown
      envelope={data as unknown as RevenueEnvelope}
      groupBy="municipio"
      onGroupByChange={() => {}}
      onExplore={() => {}}
    />,
  );
  expect(screen.getByText("Grupo 0")).toBeInTheDocument();
  expect(screen.queryByText("Grupo 24")).not.toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Próxima" }));
  expect(screen.getByText("Grupo 24")).toBeInTheDocument();
  expect(screen.getByText("Soma conhecida dos recortes")).toBeInTheDocument();
});

function mountPage(initialEntry = "/receita") {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[initialEntry]}>
        <ReceitaPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

it("mostra as janelas Gold separadas da comparação mensal e sinaliza base incompleta", async () => {
  const gold = structuredClone(response);
  gold.data.price_volume.reference_version = "gold-csv-v2";
  const v2 = {
    ...gold,
    data: {
      ...gold.data,
      window_decomposition: {
        status: "partial",
        windows: ["2023-01", "2023-12", "2024-01", "2024-12"],
        method: "metodo",
        components: {
          volume: 10,
          preco: 20,
          interacao: 1,
          entradas: 4,
          saidas: -3,
          sem_leitura: 2,
          outros: 1,
        },
        total_change_brl: 35,
        residual_brl: null,
        group_count: 3,
        incomplete_groups: 1,
        limitations: ["Somente parcelas conhecidas."],
      },
    },
  };
  vi.stubGlobal(
    "fetch",
    vi
      .fn()
      .mockResolvedValue(new Response(JSON.stringify(v2), { status: 200 })),
  );
  mountPage("/receita?competencia_inicio=2025-01&competencia_fim=2025-02");
  expect(
    await screen.findByRole("heading", { name: "Preço × volume por janela" }),
  ).toBeVisible();
  expect(screen.getByText(/2023-01 a 2023-12/)).toBeVisible();
  expect(screen.getByText(/Resultado parcial: 1 de 3/)).toBeVisible();
  expect(screen.getByText("Somente parcelas conhecidas.")).toBeVisible();
  vi.unstubAllGlobals();
});

it("mantém o período e omite identificadores técnicos na Receita", async () => {
  const gold = structuredClone(response);
  gold.metadata.source = {
    ...gold.metadata.source,
    kind: "gold_csv",
    is_demo: false,
    version: "GOLD-ARTIFICIAL:hash",
  };
  gold.data.price_volume.reference_version = "gold-csv-v2";
  gold.metadata.limitations = ["Receita paga não fornecida nesta exportação."];
  vi.stubGlobal(
    "fetch",
    vi
      .fn()
      .mockResolvedValue(new Response(JSON.stringify(gold), { status: 200 })),
  );
  mountPage("/receita?competencia_inicio=2025-01&competencia_fim=2025-02");
  expect(
    await screen.findByRole("region", { name: "Filtros aplicados" }),
  ).toBeVisible();
  expect(screen.queryByText("GOLD-ARTIFICIAL:hash")).not.toBeInTheDocument();
  expect(
    screen.queryByText(/Fonte: Gold CSV · importação local/),
  ).not.toBeInTheDocument();
  expect(
    screen.queryByRole("region", {
      name: "Período, unidades e fonte dos dados",
    }),
  ).not.toBeInTheDocument();
});

function LocationProbe() {
  const location = useLocation();
  return (
    <output aria-label="URL atual">
      {location.pathname + location.search}
    </output>
  );
}

function HistoryProbe() {
  const navigate = useNavigate();
  return (
    <button type="button" onClick={() => navigate(-1)}>
      Voltar histórico
    </button>
  );
}

function ChangeFeederProbe() {
  const [searchParams, setSearchParams] = useSearchParams();
  return (
    <button
      type="button"
      onClick={() => {
        const next = new URLSearchParams(searchParams);
        next.set("alimentador", "AL-02");
        setSearchParams(next);
      }}
    >
      Alterar alimentador para AL-02
    </button>
  );
}

describe("Receita", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("builds total, municipality, and neighborhood destinations from the current URL", () => {
    const current = new URLSearchParams({
      competencia_inicio: "2025-01",
      competencia_fim: "2025-02",
      municipio: "Olinda",
      classe: "Comercial",
      alimentador: "AL-01",
      agrupar_por: "classe",
      source: "share",
      recorte_municipio: "Olinda",
      recorte_bairro: "Centro",
      recorte_classe: "Comercial",
    });

    expect(revenueRefinementDestination(current, "municipio").toString()).toBe(
      "competencia_inicio=2025-01&competencia_fim=2025-02&municipio=Olinda&classe=Comercial&alimentador=AL-01&agrupar_por=classe&source=share&recorte_municipio=Olinda",
    );
    expect(revenueRefinementDestination(current, "bairro").toString()).toBe(
      "competencia_inicio=2025-01&competencia_fim=2025-02&municipio=Olinda&classe=Comercial&alimentador=AL-01&agrupar_por=classe&source=share&recorte_municipio=Olinda&recorte_bairro=Centro",
    );
    expect(revenueRefinementDestination(current, "total").toString()).toBe(
      "competencia_inicio=2025-01&competencia_fim=2025-02&municipio=Olinda&classe=Comercial&alimentador=AL-01&agrupar_por=classe&source=share",
    );
  });

  it("shows accumulated totals separately from endpoint comparisons and exposes an accessible series", async () => {
    const user = userEvent.setup();
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          new Response(JSON.stringify(response), { status: 200 }),
        ),
    );

    mountPage();

    const summary = await screen.findByRole("region", {
      name: "Resumo da receita",
    });
    expect(within(summary).getAllByText("Mês: Fev/2025")).toHaveLength(3);
    expect(
      within(summary).getByText("Período: Jan/2025 → Fev/2025"),
    ).toBeVisible();
    expect(within(summary).queryByText(/Mês: 2025-/)).not.toBeInTheDocument();
    expect(within(summary).getAllByText("R$ 76.500,00")[0]).toBeVisible();
    expect(
      within(summary).getByText("R$ 80.000,00").closest("p"),
    ).toHaveTextContent(/Antes: R\$\s*80\.000,00/i);
    expect(within(summary).getByText("R$ 0,8500/kWh")).toBeVisible();
    expect(
      screen.getByRole("heading", {
        name: "Preço × volume: ilustração do método",
      }),
    ).toBeVisible();
    expect(
      screen.getByText("Preço sobre volume inicial", { selector: "dt" }),
    ).toBeVisible();
    expect(
      screen.getByText("Volume a preço inicial", { selector: "dt" }),
    ).toBeVisible();
    expect(
      screen.getByText("Variação total", { selector: "dt" }),
    ).toBeVisible();
    expect(
      screen.queryByText("Ajuste de arredondamento"),
    ).not.toBeInTheDocument();
    const breakdown = screen.getByRole("region", {
      name: "Decomposição por recorte",
    });
    expect(within(breakdown).getByText("Base adequada")).toBeVisible();
    expect(within(breakdown).getByText(/Antes: 10/)).toBeVisible();
    expect(within(breakdown).getByText(/Final: 10 UCs/)).toBeVisible();
    expect(
      screen.getByText("Cobertura parcial", {
        selector: 'span[role="status"]',
      }),
    ).toBeVisible();
    expect(
      screen.queryByText("Ver acumulados e extremos"),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("table", {
        name: "Receita, energia e preço em cada extremo",
      }),
    ).not.toBeInTheDocument();
    expect(screen.getAllByText("R$ 76.500,00")).toHaveLength(2);
    expect(screen.getAllByText("R$ 80.000,00")).not.toHaveLength(0);
    expect(screen.getAllByText("−R$ 3.500,00")).toHaveLength(2);
    expect(screen.getByText("90.000 kWh")).toBeVisible();
    expect(screen.getByText(/Dados sintéticos/i)).toBeVisible();
    expect(
      screen.queryByText("Ver método, cobertura e limitações"),
    ).not.toBeInTheDocument();

    const series = screen.getByRole("region", { name: /Série mensal/i });
    expect(within(series).getByRole("table")).toBeVisible();
    expect(
      within(series).getByText(/Escala vertical inclui R\$ 0,00/),
    ).toBeVisible();
    expect(within(series).getAllByText("Jan/2025")).toHaveLength(2);
    expect(within(series).getAllByText("Fev/2025")).toHaveLength(2);
    expect(within(series).queryByText("2025-01")).not.toBeInTheDocument();
    const chart = within(series).getByRole("img", {
      name: /Receita faturada por mês/i,
    });
    expect(within(chart).getByText("Jan/2025")).toBeVisible();
    expect(within(chart).getByText("Fev/2025")).toBeVisible();
    expect(within(chart).getAllByText(/R\$/).length).toBeGreaterThan(1);
    const februaryPoint = within(chart).getByLabelText(
      "Exibir Fev/2025, faturamento R$ 76.500,00",
    );
    await user.hover(februaryPoint);
    expect(screen.getByRole("tooltip")).toHaveTextContent("Fev/2025");
    expect(screen.getByRole("tooltip")).toHaveTextContent("R$ 76.500,00");
    expect(februaryPoint).toHaveAttribute(
      "aria-describedby",
      "revenue-series-tooltip",
    );
  });

  it("shows the initial and final amounts and reconciles the visible groups", async () => {
    const recife = {
      ...response.data.breakdown.items[0],
      key: "municipio:Recife",
      label: "Recife",
      filters: {
        ...response.data.breakdown.items[0].filters,
        municipio: "Recife",
      },
      comparison: {
        ...response.data.breakdown.items[0].comparison,
        initial: {
          ...response.data.breakdown.items[0].comparison.initial,
          billed_amount: 40000,
        },
        final: {
          ...response.data.breakdown.items[0].comparison.final,
          billed_amount: 38500,
        },
        billed_amount_change_brl: -1500,
      },
    };
    const reconciled = {
      ...response,
      data: {
        ...response.data,
        breakdown: {
          ...response.data.breakdown,
          items: [...response.data.breakdown.items, recife],
          reconciliation: {
            ...response.data.breakdown.reconciliation,
            status: "available",
            initial_known_sum_brl: 80000,
            final_known_sum_brl: 76500,
            comparable_change_sum_brl: -3500,
            residual_brl: 0,
            limitations: [],
          },
        },
      },
    };
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          new Response(JSON.stringify(reconciled), { status: 200 }),
        ),
    );

    mountPage();

    const breakdown = await screen.findByRole("region", {
      name: "Decomposição por recorte",
    });
    expect(
      within(breakdown).getByRole("columnheader", { name: "Faturado inicial" }),
    ).toBeVisible();
    const olinda = within(breakdown).getByRole("row", { name: /Olinda/ });
    expect(within(olinda).getByText("R$ 40.000,00")).toBeVisible();
    expect(within(olinda).getByText("R$ 38.000,00")).toBeVisible();
    const sums = within(breakdown).getByRole("row", {
      name: /Soma conhecida dos recortes/,
    });
    expect(within(sums).getByText("R$ 80.000,00")).toBeVisible();
    expect(within(sums).getByText("R$ 76.500,00")).toBeVisible();
    expect(within(sums).getByText("−R$ 3.500,00")).toBeVisible();
    expect(
      within(breakdown).getByText("Os recortes fecham com o total."),
    ).toBeVisible();
  });

  it("identifies non-comparable groups and the unattributed difference", async () => {
    const recifeWithoutInitial = {
      ...response.data.breakdown.items[0],
      key: "municipio:Recife",
      label: "Recife",
      filters: {
        ...response.data.breakdown.items[0].filters,
        municipio: "Recife",
      },
      comparison: {
        ...response.data.breakdown.items[0].comparison,
        initial: {
          ...response.data.breakdown.items[0].comparison.initial,
          billed_amount: null,
        },
        final: {
          ...response.data.breakdown.items[0].comparison.final,
          billed_amount: 38500,
        },
        billed_amount_change_brl: null,
      },
    };
    const incomplete = {
      ...response,
      data: {
        ...response.data,
        breakdown: {
          ...response.data.breakdown,
          items: [...response.data.breakdown.items, recifeWithoutInitial],
          reconciliation: {
            status: "partial",
            initial_known_sum_brl: 40000,
            final_known_sum_brl: 76500,
            comparable_change_sum_brl: -2000,
            non_comparable_group_count: 1,
            unattributed_change_brl: -1500,
            residual_brl: null,
            limitations: [
              "Há grupos sem variação comparável entre os extremos.",
            ],
          },
        },
      },
    };
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          new Response(JSON.stringify(incomplete), { status: 200 }),
        ),
    );

    mountPage();

    const breakdown = await screen.findByRole("region", {
      name: "Decomposição por recorte",
    });
    const sums = within(breakdown).getByRole("row", {
      name: /Soma conhecida dos recortes/,
    });
    const recife = within(breakdown).getByRole("row", { name: /Recife/ });
    expect(within(recife).getAllByText("Indisponível")).toHaveLength(2);
    expect(within(sums).getByText("R$ 40.000,00")).toBeVisible();
    expect(within(sums).getByText("R$ 76.500,00")).toBeVisible();
    expect(within(sums).getByText("−R$ 2.000,00")).toBeVisible();
    expect(
      within(breakdown).getByText("1 grupo sem comparação."),
    ).toBeVisible();
    expect(
      within(breakdown)
        .getByText("−R$ 1.500,00", { selector: "span" })
        .closest("p"),
    ).toHaveTextContent("Diferença não atribuída: −R$ 1.500,00.");
    expect(
      within(breakdown).queryByText("Os recortes fecham com o total."),
    ).not.toBeInTheDocument();
  });

  it("applies base filters to the URL and request, forwarding a cancellation signal", async () => {
    const fetchMock = vi
      .fn()
      .mockImplementation(
        () => new Response(JSON.stringify(response), { status: 200 }),
      );
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    mountPage();

    const filtersTrigger = await screen.findByRole("button", {
      name: "Ajustar filtros",
    });
    await user.click(filtersTrigger);
    await screen.findByRole("heading", { name: "Ajustar filtros" });
    await screen.findByRole("option", { name: "Olinda" });
    await user.selectOptions(screen.getByLabelText("Município"), "Olinda");
    await user.selectOptions(screen.getByLabelText("Classe"), "Residencial");
    await user.click(screen.getByRole("button", { name: "Aplicar filtros" }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    const request = fetchMock.mock.calls[1];
    const url = new URL(String(request[0]), window.location.origin);
    expect(url.searchParams.get("municipio")).toBe("Olinda");
    expect(url.searchParams.get("classe")).toBe("Residencial");
    expect(url.searchParams.get("competencia_inicio")).toBe("2025-01");
    expect(url.searchParams.get("competencia_fim")).toBe("2025-02");
    expect(url.searchParams.get("group_by")).toBe("municipio");
    expect(request[1]?.signal).toBeInstanceOf(AbortSignal);
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(filtersTrigger).toHaveFocus();
  });

  it("allows filtering by neighborhood across municipalities", async () => {
    const fetchMock = vi
      .fn()
      .mockImplementation(
        () => new Response(JSON.stringify(response), { status: 200 }),
      );
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    mountPage();

    await user.click(
      await screen.findByRole("button", { name: "Ajustar filtros" }),
    );
    await user.selectOptions(
      await screen.findByLabelText("Bairro"),
      "Bairro Novo",
    );
    await user.click(screen.getByRole("button", { name: "Aplicar filtros" }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    const requestUrl = new URL(
      String(fetchMock.mock.calls[1][0]),
      window.location.origin,
    );
    expect(requestUrl.searchParams.get("bairro")).toBe("Bairro Novo");
    expect(requestUrl.searchParams.has("municipio")).toBe(false);
  });

  it("preserves a URL feeder through requests, form apply, context, and cache identity", async () => {
    const fetchMock = vi.fn((request: RequestInfo | URL) => {
      const url = new URL(String(request), window.location.origin);
      const filteredResponse = {
        ...response,
        metadata: {
          ...response.metadata,
          filters: {
            ...response.metadata.filters,
            municipio: url.searchParams.get("municipio"),
            classe: url.searchParams.get("classe"),
            alimentador: url.searchParams.get("alimentador"),
          },
        },
      };
      return Promise.resolve(
        new Response(JSON.stringify(filteredResponse), { status: 200 }),
      );
    });
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter
          initialEntries={[
            "/receita?competencia_inicio=2025-01&competencia_fim=2025-02&alimentador=AL-01",
          ]}
        >
          <ReceitaPage />
          <LocationProbe />
          <ChangeFeederProbe />
        </MemoryRouter>
      </QueryClientProvider>,
    );

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    expect(
      new URL(
        String(fetchMock.mock.calls[0][0]),
        window.location.origin,
      ).searchParams.get("alimentador"),
    ).toBe("AL-01");
    expect(screen.getByLabelText("Filtros aplicados")).toHaveTextContent(
      "Alimentador",
    );
    expect(screen.getByLabelText("Filtros aplicados")).toHaveTextContent(
      "AL-01",
    );

    await user.click(screen.getByRole("button", { name: "Ajustar filtros" }));
    await user.selectOptions(screen.getByLabelText("Município"), "Olinda");
    await user.click(screen.getByRole("button", { name: "Aplicar filtros" }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    const appliedUrl = new URL(
      String(fetchMock.mock.calls[1][0]),
      window.location.origin,
    );
    expect(appliedUrl.searchParams.get("alimentador")).toBe("AL-01");
    expect(screen.getByLabelText("URL atual")).toHaveTextContent(
      "alimentador=AL-01",
    );
    expect(screen.getByLabelText("Filtros aplicados")).toHaveTextContent(
      "AL-01",
    );

    await user.click(
      screen.getByRole("button", { name: "Alterar alimentador para AL-02" }),
    );
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3));
    expect(
      new URL(
        String(fetchMock.mock.calls[2][0]),
        window.location.origin,
      ).searchParams.get("alimentador"),
    ).toBe("AL-02");
    expect(screen.getByLabelText("Filtros aplicados")).toHaveTextContent(
      "AL-02",
    );
  });

  it("returns focus to the filter trigger after cancel and close", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(
        new Response(JSON.stringify(response), { status: 200 }),
      );
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    mountPage();

    const trigger = await screen.findByRole("button", {
      name: "Ajustar filtros",
    });
    await user.click(trigger);
    const dialog = await screen.findByRole("dialog");
    fireEvent(dialog, new Event("cancel", { bubbles: true, cancelable: true }));
    await waitFor(() => expect(trigger).toHaveFocus());

    await user.click(trigger);
    await user.click(screen.getByRole("button", { name: "Fechar filtros" }));
    await waitFor(() => expect(trigger).toHaveFocus());
  });

  it("does not send a request for a repeated scalar in the URL", () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    mountPage("/receita?competencia_inicio=2025-01&competencia_inicio=2025-02");

    expect(screen.getByRole("alert")).toHaveTextContent(/apenas uma vez/i);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it.each([
    ["alimentador", "alimentador=AL-01&alimentador=AL-02"],
    ["group_by", "group_by=municipio&group_by=bairro"],
    ["unknown", "origem=link&origem=favorito"],
  ])("blocks a repeated %s parameter before sending a request", (_, query) => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    mountPage(`/receita?${query}`);

    expect(screen.getByRole("alert")).toHaveTextContent(/apenas uma vez/i);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it.each([
    ["group_by", "group_by=municipio&group_by=bairro"],
    ["unknown", "origem=link&origem=favorito"],
  ])(
    "clears repeated %s parameters when applying valid filters",
    async (_, query) => {
      const fetchMock = vi
        .fn()
        .mockResolvedValue(
          new Response(JSON.stringify(response), { status: 200 }),
        );
      vi.stubGlobal("fetch", fetchMock);
      const user = userEvent.setup();
      const queryClient = new QueryClient({
        defaultOptions: { queries: { retry: false } },
      });
      render(
        <QueryClientProvider client={queryClient}>
          <MemoryRouter initialEntries={[`/receita?${query}&source=keep`]}>
            <ReceitaPage />
            <LocationProbe />
          </MemoryRouter>
        </QueryClientProvider>,
      );

      expect(screen.getByRole("alert")).toBeInTheDocument();
      expect(fetchMock).not.toHaveBeenCalled();
      await user.click(screen.getByRole("button", { name: "Ajustar filtros" }));
      await user.click(screen.getByRole("button", { name: "Aplicar filtros" }));

      await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
      expect(screen.queryByRole("alert")).not.toBeInTheDocument();
      expect(screen.getByLabelText("URL atual")).not.toHaveTextContent(
        /(?:group_by|origem)=.*&(?:group_by|origem)=/,
      );
      expect(screen.getByLabelText("URL atual")).toHaveTextContent(
        "source=keep",
      );
    },
  );

  it.each([
    ["empty", "alimentador="],
    ["overlong", `alimentador=${"A".repeat(101)}`],
  ])("rejects an %s feeder without requesting data", (_, query) => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    mountPage(`/receita?${query}`);

    expect(screen.getByRole("alert")).toHaveTextContent(/Alimentador/i);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("keeps a valid refinement separate from base filters when building the request", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(
        new Response(JSON.stringify(response), { status: 200 }),
      );
    vi.stubGlobal("fetch", fetchMock);

    mountPage(
      "/receita?competencia_inicio=2025-01&competencia_fim=2025-02&classe=Residencial&recorte_municipio=Olinda",
    );

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    const url = new URL(
      String(fetchMock.mock.calls[0][0]),
      window.location.origin,
    );
    expect(url.searchParams.get("municipio")).toBe("Olinda");
    expect(url.searchParams.get("classe")).toBe("Residencial");
    expect(url.searchParams.has("recorte_municipio")).toBe(false);
  });

  it("drills into a breakdown row, shows breadcrumbs, and returns to total while retaining base filters", async () => {
    const fetchMock = vi
      .fn()
      .mockImplementation(
        () => new Response(JSON.stringify(response), { status: 200 }),
      );
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter
          initialEntries={[
            "/receita?competencia_inicio=2025-01&competencia_fim=2025-02&classe=Residencial",
          ]}
        >
          <ReceitaPage />
          <LocationProbe />
          <HistoryProbe />
        </MemoryRouter>
      </QueryClientProvider>,
    );

    await user.click(
      await screen.findByRole("button", { name: "Explorar Olinda" }),
    );
    expect(screen.getByLabelText("URL atual")).toHaveTextContent(
      "recorte_municipio=Olinda",
    );
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    expect(
      await screen.findByRole("navigation", { name: "Caminho do recorte" }),
    ).toHaveTextContent("Município: Olinda");
    const drilledUrl = new URL(
      String(fetchMock.mock.calls[1][0]),
      window.location.origin,
    );
    expect(drilledUrl.searchParams.get("municipio")).toBe("Olinda");
    expect(drilledUrl.searchParams.get("classe")).toBe("Residencial");

    await user.click(screen.getByRole("button", { name: "Voltar histórico" }));
    await waitFor(() =>
      expect(screen.getByLabelText("URL atual")).not.toHaveTextContent(
        "recorte_",
      ),
    );
    await user.click(
      await screen.findByRole("button", { name: "Explorar Olinda" }),
    );
    await waitFor(() =>
      expect(screen.getByLabelText("URL atual")).toHaveTextContent(
        "recorte_municipio=Olinda",
      ),
    );

    await user.click(screen.getByRole("link", { name: "Total" }));
    expect(screen.getByLabelText("URL atual")).not.toHaveTextContent(
      "recorte_",
    );
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3));
    const totalUrl = new URL(
      String(fetchMock.mock.calls[2][0]),
      window.location.origin,
    );
    expect(totalUrl.searchParams.get("classe")).toBe("Residencial");
    expect(totalUrl.searchParams.has("municipio")).toBe(false);
  });

  it("preserves the municipality when drilling from a neighborhood row", async () => {
    let requestCount = 0;
    const neighborhoodResponse = {
      ...response,
      data: {
        ...response.data,
        breakdown: {
          ...response.data.breakdown,
          dimension: "bairro" as const,
          items: [
            {
              ...response.data.breakdown.items[0],
              key: "bairro:Recife:Centro",
              label: "Centro",
              filters: {
                municipio: "Recife",
                bairro: "Centro",
                classe: null,
                alimentador: null,
              },
            },
            {
              ...response.data.breakdown.items[0],
              key: "bairro:Olinda:Centro",
              label: "Centro",
              filters: {
                municipio: "Olinda",
                bairro: "Centro",
                classe: null,
                alimentador: null,
              },
            },
          ],
        },
      },
    };
    const fetchMock = vi.fn((request: RequestInfo | URL) => {
      void request;
      requestCount += 1;
      return Promise.resolve(
        new Response(
          JSON.stringify(requestCount === 1 ? response : neighborhoodResponse),
          { status: 200 },
        ),
      );
    });
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={["/receita"]}>
          <ReceitaPage />
          <LocationProbe />
        </MemoryRouter>
      </QueryClientProvider>,
    );

    await user.click(
      await screen.findByRole("button", { name: "Explorar Olinda" }),
    );
    expect(
      await screen.findByRole("button", { name: "Explorar Centro · Recife" }),
    ).toBeVisible();
    await user.click(
      screen.getByRole("button", { name: "Explorar Centro · Olinda" }),
    );
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3));

    const location = screen.getByLabelText("URL atual");
    expect(location).toHaveTextContent("recorte_municipio=Olinda");
    expect(location).toHaveTextContent("recorte_bairro=Centro");
    const request = new URL(
      String(fetchMock.mock.calls[2][0]),
      window.location.origin,
    );
    expect(request.searchParams.get("municipio")).toBe("Olinda");
    expect(request.searchParams.get("bairro")).toBe("Centro");
  });

  it("uses the breadcrumb destination for both its href and browser navigation", async () => {
    const initialSearch =
      "competencia_inicio=2025-01&competencia_fim=2025-02&municipio=Olinda&classe=Comercial&alimentador=AL-01&agrupar_por=classe&source=share&recorte_municipio=Olinda&recorte_bairro=Centro&recorte_classe=Comercial";
    const municipalitySearch =
      "competencia_inicio=2025-01&competencia_fim=2025-02&municipio=Olinda&classe=Comercial&alimentador=AL-01&agrupar_por=classe&source=share&recorte_municipio=Olinda";
    const neighborhoodSearch =
      "competencia_inicio=2025-01&competencia_fim=2025-02&municipio=Olinda&classe=Comercial&alimentador=AL-01&agrupar_por=classe&source=share&recorte_municipio=Olinda&recorte_bairro=Centro";
    const totalSearch =
      "competencia_inicio=2025-01&competencia_fim=2025-02&municipio=Olinda&classe=Comercial&alimentador=AL-01&agrupar_por=classe&source=share";
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          new Response(JSON.stringify(response), { status: 200 }),
        ),
    );
    const user = userEvent.setup();
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={[`/receita?${initialSearch}`]}>
          <ReceitaPage />
          <LocationProbe />
          <HistoryProbe />
        </MemoryRouter>
      </QueryClientProvider>,
    );

    const municipalityLink = await screen.findByRole("link", {
      name: /Município: Olinda/,
    });
    const explored = screen.getByRole("region", { name: "Recorte explorado" });
    expect(explored).toHaveTextContent(
      "Explorando: Município: Olinda · Bairro: Centro · Classe: Comercial",
    );
    expect(
      within(explored).getByRole("button", { name: "Voltar ao total" }),
    ).toBeVisible();
    expect(municipalityLink).toHaveAttribute("href", `?${municipalitySearch}`);
    const neighborhoodLink = screen.getByRole("link", {
      name: /Bairro: Centro/,
    });
    expect(neighborhoodLink).toHaveAttribute("href", `?${neighborhoodSearch}`);
    await user.click(neighborhoodLink);
    await waitFor(() =>
      expect(screen.getByLabelText("URL atual")).toHaveTextContent(
        neighborhoodSearch,
      ),
    );

    await user.click(screen.getByRole("button", { name: "Voltar histórico" }));
    await waitFor(() =>
      expect(screen.getByLabelText("URL atual")).toHaveTextContent(
        initialSearch,
      ),
    );
    await user.click(municipalityLink);
    await waitFor(() =>
      expect(screen.getByLabelText("URL atual")).toHaveTextContent(
        municipalitySearch,
      ),
    );

    await user.click(screen.getByRole("button", { name: "Voltar histórico" }));
    await waitFor(() =>
      expect(screen.getByLabelText("URL atual")).toHaveTextContent(
        initialSearch,
      ),
    );
    const totalLink = await screen.findByRole("link", { name: "Total" });
    expect(totalLink).toHaveAttribute("href", `?${totalSearch}`);
    await user.click(screen.getByRole("button", { name: "Voltar ao total" }));
    await waitFor(() =>
      expect(screen.getByLabelText("URL atual")).toHaveTextContent(totalSearch),
    );
  });

  it("returns from a municipality refinement to the municipality when only class remains", async () => {
    const initialSearch =
      "competencia_inicio=2025-01&competencia_fim=2025-02&municipio=Olinda&classe=Comercial&alimentador=AL-01&agrupar_por=classe&recorte_municipio=Olinda&recorte_classe=Comercial";
    const municipalitySearch =
      "competencia_inicio=2025-01&competencia_fim=2025-02&municipio=Olinda&classe=Comercial&alimentador=AL-01&agrupar_por=classe&recorte_municipio=Olinda";
    const fetchMock = vi
      .fn()
      .mockResolvedValue(
        new Response(JSON.stringify(response), { status: 200 }),
      );
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={[`/receita?${initialSearch}`]}>
          <ReceitaPage />
          <LocationProbe />
        </MemoryRouter>
      </QueryClientProvider>,
    );

    const municipalityLink = await screen.findByRole("link", {
      name: /Município: Olinda/,
    });
    expect(municipalityLink).toHaveAttribute("href", `?${municipalitySearch}`);
    await user.click(municipalityLink);
    await waitFor(() =>
      expect(screen.getByLabelText("URL atual")).toHaveTextContent(
        municipalitySearch,
      ),
    );
  });

  it("keeps the neighborhood as the current breadcrumb when there is no class refinement", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          new Response(JSON.stringify(response), { status: 200 }),
        ),
    );
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter
          initialEntries={[
            "/receita?competencia_inicio=2025-01&competencia_fim=2025-02&recorte_municipio=Olinda&recorte_bairro=Centro",
          ]}
        >
          <ReceitaPage />
        </MemoryRouter>
      </QueryClientProvider>,
    );

    const neighborhood = await screen.findByText("Bairro: Centro");
    expect(neighborhood.tagName).toBe("SPAN");
    expect(neighborhood).toHaveAttribute("aria-current", "page");
  });

  it("rejects long and contradictory refinements without requesting data", () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    mountPage(`/receita?municipio=Recife&recorte_municipio=${"x".repeat(101)}`);

    expect(screen.getByRole("alert")).toHaveTextContent(
      /não pode contradizer/i,
    );
    expect(screen.getByRole("alert")).toHaveTextContent(/100 caracteres/i);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("renders missing-value markers as human labels in context and neighborhood actions", async () => {
    const sentinel = "__grid360_missing__";
    const missingValueResponse = {
      ...response,
      data: {
        ...response.data,
        breakdown: {
          ...response.data.breakdown,
          dimension: "bairro",
          items: response.data.breakdown.items.map((item) => ({
            ...item,
            label: sentinel,
            filters: {
              ...item.filters,
              municipio: sentinel,
              bairro: sentinel,
            },
          })),
        },
      },
      metadata: {
        ...response.metadata,
        filters: {
          municipio: sentinel,
          bairro: null,
          classe: null,
          alimentador: null,
        },
      },
    };
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          new Response(JSON.stringify(missingValueResponse), { status: 200 }),
        ),
    );

    mountPage(`/receita?agrupar_por=bairro&recorte_municipio=${sentinel}`);

    expect(
      await screen.findByRole("button", {
        name: "Explorar Não informado · Não informado",
      }),
    ).toBeVisible();
    expect(screen.getByLabelText("Filtros aplicados")).toHaveTextContent(
      "Não informado",
    );
    expect(
      screen.getByRole("navigation", { name: "Caminho do recorte" }),
    ).toHaveTextContent("Município: Não informado");
    expect(document.body).not.toHaveTextContent(sentinel);
  });

  it("clears refinements when a new base filter is applied", async () => {
    const fetchMock = vi
      .fn()
      .mockImplementation(
        () => new Response(JSON.stringify(response), { status: 200 }),
      );
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter
          initialEntries={[
            "/receita?competencia_inicio=2025-01&competencia_fim=2025-02&recorte_municipio=Olinda",
          ]}
        >
          <ReceitaPage />
          <LocationProbe />
        </MemoryRouter>
      </QueryClientProvider>,
    );

    await screen.findByText("Ajustar filtros");
    await user.click(screen.getByText("Ajustar filtros"));
    await screen.findByRole("option", { name: "Recife" });
    await user.selectOptions(screen.getByLabelText("Município"), "Recife");
    await user.click(screen.getByRole("button", { name: "Aplicar filtros" }));
    expect(screen.getByLabelText("URL atual")).toHaveTextContent(
      "municipio=Recife",
    );
    expect(screen.getByLabelText("URL atual")).not.toHaveTextContent(
      "recorte_",
    );
  });

  it("aborts an obsolete request when the effective filter query changes", async () => {
    const signals: AbortSignal[] = [];
    const fetchMock = vi.fn((_: RequestInfo | URL, init?: RequestInit) => {
      const call = signals.length;
      signals.push(init?.signal as AbortSignal);
      if (call === 1) {
        return new Promise<Response>(() => undefined);
      }
      return Promise.resolve(
        new Response(JSON.stringify(response), { status: 200 }),
      );
    });
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    mountPage();

    await screen.findByText("Ajustar filtros");
    await user.click(screen.getByText("Ajustar filtros"));
    await screen.findByRole("option", { name: "Olinda" });
    await user.selectOptions(screen.getByLabelText("Município"), "Olinda");
    await user.click(screen.getByRole("button", { name: "Aplicar filtros" }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    await user.click(screen.getByRole("button", { name: "Ajustar filtros" }));
    await user.selectOptions(screen.getByLabelText("Mês do fim"), "03");
    await user.click(screen.getByRole("button", { name: "Aplicar filtros" }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3));

    expect(signals[1].aborted).toBe(true);
    expect(signals[2].aborted).toBe(false);
  });

  it("rejects an unsupported contract version at runtime", async () => {
    const invalidResponse = {
      ...response,
      metadata: { ...response.metadata, contract_version: "1.0.0" },
    };
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          new Response(JSON.stringify(invalidResponse), { status: 200 }),
        ),
    );

    mountPage();

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Não foi possível consultar a receita",
    );
    expect(screen.queryByText("R$ 76.500,00")).not.toBeInTheDocument();
  });

  it("shows service errors and retries the same revenue query", async () => {
    let requestCount = 0;
    const fetchMock = vi.fn(() => {
      requestCount += 1;
      return Promise.resolve(
        requestCount === 1
          ? new Response(
              JSON.stringify({ detail: "temporarily unavailable" }),
              {
                status: 503,
              },
            )
          : new Response(JSON.stringify(response), { status: 200 }),
      );
    });
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    mountPage();

    expect(await screen.findByRole("alert")).toHaveTextContent("HTTP 503");
    await user.click(screen.getByRole("button", { name: "Tentar novamente" }));
    await screen.findByRole("heading", {
      name: "Preço × volume: ilustração do método",
    });
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("shows base size and suppresses percentages for a small base", async () => {
    const smallBaseResponse = {
      ...response,
      data: {
        ...response.data,
        comparison: {
          ...response.data.comparison,
          initial: { ...response.data.comparison.initial, billed_uc_count: 4 },
          final: { ...response.data.comparison.final, billed_uc_count: 4 },
          billed_amount_change_percent: null,
        },
        quality: {
          ...response.data.quality,
          small_base: true,
          percent_change_eligible: false,
        },
        breakdown: {
          ...response.data.breakdown,
          items: response.data.breakdown.items.map((item) => ({
            ...item,
            comparison: {
              ...item.comparison,
              initial: { ...item.comparison.initial, billed_uc_count: 4 },
              final: { ...item.comparison.final, billed_uc_count: 4 },
              billed_amount_change_percent: null,
            },
            quality: {
              ...item.quality,
              small_base: true,
              percent_change_eligible: false,
            },
          })),
        },
      },
    };
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          new Response(JSON.stringify(smallBaseResponse), { status: 200 }),
        ),
    );

    mountPage();

    const breakdown = await screen.findByRole("region", {
      name: "Decomposição por recorte",
    });
    expect(within(breakdown).getByText("Base pequena")).toBeVisible();
    expect(within(breakdown).getByText(/Antes: 4/)).toBeVisible();
    expect(within(breakdown).getByText(/Final: 4 UCs/)).toBeVisible();
    expect(
      within(
        screen.getByRole("region", { name: "Resumo da receita" }),
      ).getByText("Percentual indisponível"),
    ).toBeVisible();
  });

  it("keeps an absolute delta but withholds price-volume effects when initial revenue is zero", async () => {
    const zeroInitialResponse = {
      ...response,
      data: {
        ...response.data,
        comparison: {
          ...response.data.comparison,
          initial: {
            ...response.data.comparison.initial,
            billed_amount: 0,
            observed_price_brl_per_kwh: 0,
          },
          billed_amount_change_brl: 76500,
          billed_amount_change_percent: null,
        },
        price_volume: {
          ...response.data.price_volume,
          price_effect_brl: null,
          volume_effect_brl: null,
          interaction_effect_brl: null,
          rounding_adjustment_brl: null,
          status: "unavailable",
        },
        quality: { ...response.data.quality, percent_change_eligible: false },
      },
    };
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          new Response(JSON.stringify(zeroInitialResponse), { status: 200 }),
        ),
    );

    mountPage();

    expect(await screen.findAllByText("+R$ 76.500,00")).toHaveLength(2);
    const decomposition = screen.getByRole("region", {
      name: "Preço × volume: ilustração do método",
    });
    expect(within(decomposition).getAllByText("Indisponível")).toHaveLength(3);
  });

  it("shows an explicit rounding adjustment only when the API publishes a nonzero amount", async () => {
    const adjustedResponse = {
      ...response,
      data: {
        ...response.data,
        price_volume: {
          ...response.data.price_volume,
          volume_effect_brl: -8000.01,
          rounding_adjustment_brl: 0.01,
        },
      },
    };
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          new Response(JSON.stringify(adjustedResponse), { status: 200 }),
        ),
    );

    mountPage();

    expect(
      await screen.findByText("Ajuste de arredondamento", { selector: "dt" }),
    ).toBeVisible();
    expect(screen.getByText("+R$ 0,01")).toBeVisible();
  });

  it("reports missing financial coverage and keeps the comparison unavailable", async () => {
    const incompleteResponse = {
      ...response,
      data: {
        ...response.data,
        series: response.data.series.map((row, index) =>
          index === 1 ? { ...row, billed_amount: null } : row,
        ),
        comparison: {
          ...response.data.comparison,
          final: {
            ...response.data.comparison.final,
            billed_amount: null,
          },
          billed_amount_change_brl: null,
          billed_amount_change_percent: null,
        },
        price_volume: {
          ...response.data.price_volume,
          price_effect_brl: null,
          volume_effect_brl: null,
          interaction_effect_brl: null,
          rounding_adjustment_brl: null,
          status: "unavailable",
        },
        coverage: {
          ...response.data.coverage,
          billed_amount: {
            status: "partial",
            covered_months: ["2025-01"],
            missing_months: ["2025-02"],
            limitations: ["Faturamento de fevereiro sem cobertura."],
          },
        },
        quality: { ...response.data.quality, percent_change_eligible: false },
      },
      metadata: { ...response.metadata, status: "partial" },
    };
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          new Response(JSON.stringify(incompleteResponse), { status: 200 }),
        ),
    );
    mountPage();

    expect(await screen.findByText("Cobertura parcial")).toBeVisible();
    expect(screen.getAllByText("Indisponível").length).toBeGreaterThan(0);
    expect(
      screen.queryByText("Ver método, cobertura e limitações"),
    ).not.toBeInTheDocument();
  });

  it("represents empty data and null amounts without converting absence to zero", async () => {
    const emptyResponse = {
      ...response,
      data: {
        ...response.data,
        total_billed_amount: null,
        total_paid_amount: null,
        total_measured_energy_kwh: null,
        total_billed_energy_kwh: null,
        observed_price_brl_per_kwh: null,
        series: response.data.series.map((row) => ({
          ...row,
          billed_amount: null,
          paid_amount: null,
          measured_energy_kwh: null,
          billed_energy_kwh: null,
        })),
        comparison: {
          ...response.data.comparison,
          initial: {
            ...response.data.comparison.initial,
            billed_amount: null,
            billed_energy_kwh: null,
            observed_price_brl_per_kwh: null,
            billed_uc_count: null,
            status: "empty",
          },
          final: {
            ...response.data.comparison.final,
            billed_amount: null,
            billed_energy_kwh: null,
            observed_price_brl_per_kwh: null,
            billed_uc_count: null,
            status: "empty",
          },
          billed_amount_change_brl: null,
          billed_energy_change_kwh: null,
          measured_energy_change_kwh: null,
          billed_amount_change_percent: null,
        },
        price_volume: {
          ...response.data.price_volume,
          price_effect_brl: null,
          volume_effect_brl: null,
          interaction_effect_brl: null,
          rounding_adjustment_brl: null,
          status: "unavailable",
        },
        coverage: {
          requested_months: ["2025-01", "2025-02"],
          billed_amount: {
            status: "empty",
            covered_months: [],
            missing_months: ["2025-01", "2025-02"],
            limitations: [],
          },
          billed_energy_kwh: {
            status: "empty",
            covered_months: [],
            missing_months: ["2025-01", "2025-02"],
            limitations: [],
          },
          paid_amount: {
            status: "empty",
            covered_months: [],
            missing_months: ["2025-01", "2025-02"],
            limitations: [],
          },
          measured_energy_kwh: {
            status: "empty",
            covered_months: [],
            missing_months: ["2025-01", "2025-02"],
            limitations: [],
          },
        },
        breakdown: {
          ...response.data.breakdown,
          items: [],
          reconciliation: {
            status: "empty",
            initial_known_sum_brl: null,
            final_known_sum_brl: null,
            comparable_change_sum_brl: null,
            non_comparable_group_count: 0,
            unattributed_change_brl: null,
            residual_brl: null,
            limitations: [],
          },
        },
        quality: { ...response.data.quality, percent_change_eligible: false },
      },
      metadata: { ...response.metadata, status: "empty" },
    };
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          new Response(JSON.stringify(emptyResponse), { status: 200 }),
        ),
    );

    mountPage();

    expect(
      await screen.findByText(/Sem registros para este recorte/i),
    ).toBeVisible();
    expect(screen.getAllByText("Indisponível").length).toBeGreaterThan(0);
    expect(screen.queryByText("R$ 0,00")).not.toBeInTheDocument();
    expect(screen.getByText(/A consulta não retornou grupos/i)).toBeVisible();
  });
});
