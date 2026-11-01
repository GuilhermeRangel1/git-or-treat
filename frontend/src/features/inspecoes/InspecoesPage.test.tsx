import { beforeEach, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, useLocation } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import InspecoesPage from "./InspecoesPage";
import { decodeDetail, decodeQueue } from "./contract";

const item = {
  uc_id: "UC-1004",
  municipality: "Recife",
  neighborhood: "Centro",
  class_name: "Residencial",
  feeder_id: "AL-03",
  priority: 0.92,
  reason: "Lacuna de leitura e medidor retirado",
  potential_recoverable_energy_kwh: 45,
  indicators: ["reading_gap", "meter_removed"],
  signals: [
    { id: "reading_gap", label: "Lacuna de leitura", weight: 0.6 },
    { id: "meter_removed", label: "Medidor retirado", weight: 0.32 },
  ],
};
const second = {
  ...item,
  uc_id: "UC-1002",
  priority: 0.61,
  potential_recoverable_energy_kwh: null,
};
const metadata = {
  contract_version: "1.0.0",
  status: "partial",
  period: { start: "2025-01", end: "2025-02" },
  source: {
    kind: "synthetic",
    version: "dev03-v1",
    is_demo: true,
    updated_at: "2026-10-21T00:00:00Z",
  },
  limitations: ["Dados sintéticos."],
};
const options = {
  municipio: ["Olinda", "Recife"],
  bairro: ["Centro"],
  classe: ["Residencial"],
  alimentador: ["AL-03"],
};
function envelope(
  items = [item, second],
  page = 1,
  size = 10,
  total = items.length,
) {
  return {
    data: {
      items,
      filter_options: options,
      summary: {
        total_units: total,
        highest_priority: total ? 0.92 : null,
        estimated_units: total ? 1 : 0,
        unavailable_estimate_units: Math.max(0, total - 1),
      },
    },
    pagination: {
      page,
      page_size: size,
      total,
      total_pages: Math.ceil(total / size),
    },
    metadata,
  };
}
const detail = {
  data: {
    ...item,
    rule_version: "dev05-v1",
    signals: [
      { id: "reading_gap", label: "Lacuna de leitura", weight: 0.6 },
      { id: "meter_removed", label: "Medidor retirado", weight: 0.32 },
    ],
    estimate_evidence: {
      baseline_kwh: 90,
      observed_kwh: 45,
      horizon_months: 1,
      reference: "Cenário sintético de um mês.",
      unavailable_reason: null,
    },
    limitations: ["Suspeita não confirma irregularidade."],
  },
  metadata,
};
function Location() {
  return <span aria-label="URL atual">{useLocation().search}</span>;
}
function mount(
  url = "/inspecoes",
  client = new QueryClient({ defaultOptions: { queries: { retry: false } } }),
) {
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[url]}>
        <InspecoesPage />
        <Location />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}
function respond(value: unknown, status = 200) {
  return new Response(JSON.stringify(value), { status });
}
async function firstEvidenceLink() {
  return (
    await screen.findAllByRole("link", { name: "Ver evidência de UC-1004" })
  )[0];
}
beforeEach(() => {
  vi.restoreAllMocks();
});

it("mostra origem e unidades sem atribuir à fila o período do consumo", async () => {
  const gold = envelope([
    { ...item, priority: 0.92, potential_recoverable_energy_kwh: null },
  ]);
  gold.metadata = {
    ...gold.metadata,
    source: {
      ...metadata.source,
      kind: "gold_csv",
      version: "GOLD-ARTIFICIAL:hash",
      is_demo: false,
    },
    limitations: ["A fila não informa janela temporal própria."],
  };
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(respond(gold)));
  mount();
  const panel = await screen.findByRole("region", {
    name: "Período, unidades e fonte dos dados",
  });
  expect(within(panel).getByText("Cobertura do consumo no lote")).toBeVisible();
  expect(within(panel).getByText("01/2025 a 02/2025")).toBeVisible();
  expect(within(panel).getByText("GOLD-ARTIFICIAL:hash")).toBeVisible();
  expect(within(panel).getByText("Identificação da publicação")).toBeVisible();
  expect(
    within(panel).getByText(
      /não indica necessariamente quando foram coletados/,
    ),
  ).toBeVisible();
  expect(within(panel).getByText(/UCs · inspeções · kWh/)).toBeVisible();
  expect(
    within(panel).getByText("A fila não informa janela temporal própria."),
  ).toBeVisible();
});

it("na Gold v2 desativa ordenação por energia e preserva a volta do detalhe", async () => {
  const goldItem = {
    ...item,
    priority: null,
    priority_label: "ALTA - HISTORICO IRREGULAR",
    reason: "Histórico confirmado",
    potential_recoverable_energy_kwh: null,
    signals: [],
  };
  const goldMetadata = {
    ...metadata,
    source: {
      ...metadata.source,
      kind: "gold_csv",
      is_demo: false,
      version: "gold-csv-v2:artificial:publicacao",
    },
  };
  const queue = {
    ...envelope(),
    data: {
      ...envelope().data,
      items: [goldItem],
      neighborhoods: [
        { municipio: "Recife", bairro: "Centro" },
        { municipio: "Olinda", bairro: "Bairro Novo" },
      ],
      summary: {
        total_units: 1,
        highest_priority: null,
        estimated_units: 0,
        unavailable_estimate_units: 1,
      },
    },
    pagination: { page: 1, page_size: 10, total: 1, total_pages: 1 },
    metadata: goldMetadata,
  };
  const evidence = {
    data: {
      ...goldItem,
      rule_version: "gold-csv-v2",
      historical_recovery: {
        mean_kwh_per_inspection: 20,
        lower_kwh_per_inspection: 5,
        upper_kwh_per_inspection: 40,
        reference: "global",
      },
      estimate_evidence: {
        baseline_kwh: null,
        observed_kwh: null,
        horizon_months: null,
        reference: "Não informado",
        unavailable_reason: "Estimativa ausente",
      },
      limitations: [],
    },
    metadata: goldMetadata,
  };
  vi.stubGlobal(
    "fetch",
    vi
      .fn()
      .mockImplementation(async (url: string) =>
        respond(url.includes("/queue/UC-") ? evidence : queue),
      ),
  );
  const user = userEvent.setup();
  mount("/inspecoes?municipio=Recife&page=1");
  await firstEvidenceLink();
  await user.click(screen.getByRole("button", { name: /Ajustar filtros/ }));
  expect(
    screen.getByRole("option", { name: /Energia estimada \(indisponível\)/ }),
  ).toBeDisabled();
  await user.selectOptions(screen.getByLabelText("Município"), "Olinda");
  expect(
    screen.getByRole("option", { name: "Bairro Novo" }),
  ).toBeInTheDocument();
  expect(
    screen.queryByRole("option", { name: "Centro" }),
  ).not.toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Fechar filtros" }));
  await user.click(
    (
      await screen.findAllByRole("link", { name: "Ver evidência de UC-1004" })
    )[0],
  );
  expect(await screen.findByText("Histórico confirmado")).toBeVisible();
  expect(
    screen.getByText("Média histórica de recuperação por inspeção"),
  ).toBeVisible();
  expect(screen.getByText(/não é estimativa para esta UC/)).toBeVisible();
  expect(
    screen.getByText(/A fila não informa uma janela temporal própria/),
  ).toBeVisible();
  await user.click(screen.getByRole("button", { name: "Ver fundamentos" }));
  expect(screen.getAllByText("Não informado").length).toBeGreaterThan(0);
  expect(
    screen.queryByText(/Regra: máximo entre zero/),
  ).not.toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Fechar fundamentos" }));
  await user.click(screen.getByRole("link", { name: "Voltar à fila" }));
  expect(screen.getByLabelText("URL atual")).toHaveTextContent(
    "municipio=Recife&page=1",
  );
});

it("oferece recuperação para link antigo com ordenação por energia indisponível", async () => {
  vi.stubGlobal(
    "fetch",
    vi
      .fn()
      .mockImplementation(async (url: string) =>
        url.includes("potential_recoverable_energy_kwh")
          ? respond({ error: { code: "estimate_sort_unavailable" } }, 422)
          : respond(envelope()),
      ),
  );
  const user = userEvent.setup();
  mount("/inspecoes?order_by=potential_recoverable_energy_kwh");
  await user.click(
    await screen.findByRole("button", { name: "Ordenar por prioridade" }),
  );
  await waitFor(() =>
    expect(screen.getByLabelText("URL atual")).not.toHaveTextContent(
      "order_by=",
    ),
  );
  expect(await firstEvidenceLink()).toBeVisible();
});

it("abre evidências reproduzíveis e volta preservando a página e os filtros", async () => {
  const fetch = vi
    .fn()
    .mockImplementation(async (url: string) =>
      url.includes("/queue/UC-")
        ? respond(detail)
        : respond(envelope([item], 2, 1, 2)),
    );
  vi.stubGlobal("fetch", fetch);
  const user = userEvent.setup();
  mount("/inspecoes?municipio=Recife&page_size=1&page=2");
  expect(await firstEvidenceLink()).toBeVisible();
  await user.click(
    (
      await screen.findAllByRole("link", { name: "Ver evidência de UC-1004" })
    )[0],
  );
  expect(await screen.findByText("O que motivou a investigação")).toBeVisible();
  expect(
    screen.getByLabelText("Prioridade analítica: 0,92 de 1"),
  ).toBeVisible();
  expect(screen.getByText("45 kWh")).toBeVisible();
  expect(screen.getByText(/não constitui diagnóstico de fraude/)).toBeVisible();
  expect(
    screen.getByRole("button", { name: "Criar ordem de inspeção" }),
  ).toBeEnabled();
  await user.click(screen.getByRole("button", { name: "Ver fundamentos" }));
  expect(
    await screen.findByRole("heading", {
      name: "Como a prioridade foi calculada",
    }),
  ).toBeVisible();
  expect(
    screen.getByText(/Atualizado em 21\/10\/2026, 00:00:00 UTC/),
  ).toBeVisible();
  expect(screen.getAllByText("0,92 / 1")).toHaveLength(1);
  expect(screen.getByText("max(0; 90 − 45) × 1 = 45 kWh")).toBeVisible();
  const comparison = screen.getByRole("region", {
    name: "Comparativo de consumo",
  });
  expect(within(comparison).getByText("90 kWh/mês")).toBeVisible();
  expect(within(comparison).getByText("45 kWh/mês")).toBeVisible();
  expect(screen.getByLabelText("Composição da prioridade")).toHaveTextContent(
    "min(1; 0,6 + 0,32) = 0,92",
  );
  expect(
    screen.getByRole("heading", { name: "O que define a posição na fila" }),
  ).toBeVisible();
  await user.click(screen.getByRole("link", { name: "Voltar à fila" }));
  expect(await screen.findByText(/Página 2 de 2/)).toBeVisible();
  expect(screen.getByLabelText("URL atual")).toHaveTextContent(
    "municipio=Recife&page_size=1&page=2",
  );
});

it("após conflito obsoleto, atualiza o detalhe e cria nova intenção com dados novos", async () => {
  const updatedDetail = {
    ...detail,
    data: { ...detail.data, rule_version: "dev05-v2" },
    metadata: {
      ...metadata,
      source: { ...metadata.source, version: "dev03-v2" },
    },
  };
  let detailReads = 0;
  let createAttempts = 0;
  const fetch = vi
    .fn()
    .mockImplementation((url: string, options?: RequestInit) => {
      if (url.includes("/queue/UC-") && options?.method !== "POST") {
        detailReads += 1;
        return Promise.resolve(
          respond(detailReads === 1 ? detail : updatedDetail),
        );
      }
      if (options?.method === "POST") {
        createAttempts += 1;
        return Promise.resolve(
          createAttempts === 1
            ? respond(
                {
                  detail: "A suspeita mudou.",
                  error: {
                    code: "stale_suspicion",
                    message: "A suspeita mudou.",
                  },
                },
                409,
              )
            : respond(
                {
                  id: 42,
                  uc_id: "UC-1004",
                  reason: item.reason,
                  priority: "MEDIA",
                  status: "PENDENTE",
                  notes: null,
                  result: null,
                  created_at: "2026-10-23T12:00:00Z",
                  updated_at: "2026-10-23T12:00:00Z",
                  suspicion_reference: "reference",
                  version: 1,
                  cancellation_reason: null,
                },
                201,
              ),
        );
      }
      return Promise.resolve(respond(envelope()));
    });
  vi.stubGlobal("fetch", fetch);
  const user = userEvent.setup();
  mount("/inspecoes?uc=UC-1004");
  await screen.findByRole("button", { name: "Criar ordem de inspeção" });
  await user.click(
    screen.getByRole("button", { name: "Criar ordem de inspeção" }),
  );
  await screen.findByText(/A suspeita mudou desde a consulta/);
  await user.click(
    screen.getByRole("button", { name: "Atualizar dados da suspeita" }),
  );
  await waitFor(() => expect(detailReads).toBe(2));
  await user.click(
    screen.getByRole("button", { name: "Criar ordem de inspeção" }),
  );
  await screen.findByText(/Ordem 42 confirmada pelo servidor/);

  const writes = fetch.mock.calls.filter(
    ([, options]) => options?.method === "POST",
  );
  expect(writes).toHaveLength(2);
  expect(writes[1][1]?.headers).not.toEqual(writes[0][1]?.headers);
  expect(writes[0][1]?.body).toBe(
    JSON.stringify({ source_version: "dev03-v1", rule_version: "dev05-v1" }),
  );
  expect(writes[1][1]?.body).toBe(
    JSON.stringify({ source_version: "dev03-v2", rule_version: "dev05-v2" }),
  );
});

it("aplica filtros e ordenação na API, reiniciando a página, e trata fila vazia", async () => {
  const fetch = vi
    .fn()
    .mockImplementation(async (url: string) =>
      respond(url.includes("municipio=Olinda") ? envelope([]) : envelope()),
    );
  vi.stubGlobal("fetch", fetch);
  const user = userEvent.setup();
  mount();
  await firstEvidenceLink();
  expect(screen.getByText("jan/2025 – fev/2025")).toBeVisible();
  expect(screen.getByText("Não aplicada")).toBeVisible();
  await user.click(screen.getByRole("button", { name: "Ajustar filtros" }));
  await user.selectOptions(screen.getByLabelText("Município"), "Olinda");
  await user.selectOptions(
    screen.getByLabelText("Ordenar por"),
    "potential_recoverable_energy_kwh",
  );
  await user.selectOptions(screen.getByLabelText("Ordenar por"), "uc_id");
  await user.selectOptions(screen.getByLabelText("Direção"), "asc");
  await user.selectOptions(screen.getByLabelText("Direção"), "desc");
  await user.selectOptions(screen.getByLabelText("Direção"), "asc");
  await user.selectOptions(screen.getByLabelText("UCs por página"), "20");
  await user.selectOptions(screen.getByLabelText("UCs por página"), "50");
  await user.click(screen.getByRole("button", { name: "Aplicar filtros" }));
  expect(
    await screen.findByText(
      "Nenhuma suspeita neste recorte. Isso não comprova ausência de perdas.",
    ),
  ).toBeVisible();
  const url = new URL(fetch.mock.calls.at(-1)![0], window.location.origin);
  expect(url.searchParams.get("municipio")).toBe("Olinda");
  expect(url.searchParams.get("order_by")).toBe("uc_id");
  expect(url.searchParams.get("direction")).toBe("asc");
  expect(url.searchParams.get("page_size")).toBe("50");
  expect(url.searchParams.get("page")).toBe("1");
});

it("mostra e remove o alimentador ativo no resumo e na consulta", async () => {
  const fetch = vi.fn().mockResolvedValue(respond(envelope()));
  vi.stubGlobal("fetch", fetch);
  const user = userEvent.setup();
  mount();
  await firstEvidenceLink();

  await user.click(screen.getByRole("button", { name: /Ajustar filtros/ }));
  await user.selectOptions(screen.getByLabelText("Alimentador"), "AL-03");
  await user.click(screen.getByRole("button", { name: "Aplicar filtros" }));

  expect(await screen.findByText("Alimentador: AL-03")).toBeVisible();
  await waitFor(() => {
    const request = new URL(
      fetch.mock.calls.at(-1)![0],
      window.location.origin,
    );
    expect(request.searchParams.get("alimentador")).toBe("AL-03");
  });
  expect(screen.getByLabelText("URL atual")).toHaveTextContent(
    "alimentador=AL-03",
  );

  await user.click(screen.getByRole("button", { name: /Ajustar filtros/ }));
  await user.click(screen.getByRole("button", { name: "Limpar filtros" }));
  await waitFor(() => {
    expect(screen.getByLabelText("URL atual")).not.toHaveTextContent(
      "alimentador=",
    );
  });
  expect(screen.queryByText("Alimentador: AL-03")).not.toBeInTheDocument();
});

it("pagina pelo servidor e mantém estimativa ausente distinta de zero", async () => {
  const fetch = vi
    .fn()
    .mockImplementation(async (url: string) =>
      respond(
        url.includes("page=2")
          ? envelope([second], 2, 1, 2)
          : envelope([item], 1, 1, 2),
      ),
    );
  vi.stubGlobal("fetch", fetch);
  const user = userEvent.setup();
  mount("/inspecoes?page_size=1");
  await screen.findByText(/Página 1 de 2/);
  await user.click(screen.getByRole("button", { name: "Próxima" }));
  expect(await screen.findByText(/Página 2 de 2/)).toBeVisible();
  expect(screen.getAllByText("Estimativa indisponível")).toHaveLength(2);
  expect(
    screen.queryByRole("region", { name: "Resumo do recorte da fila" }),
  ).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Ver fundamentos" })).toBeVisible();
  expect(screen.getByRole("button", { name: "Próxima" })).toBeDisabled();
});

it("mantém filtros como rascunho no diálogo e fecha com Escape devolvendo foco", async () => {
  const fetch = vi.fn().mockResolvedValue(respond(envelope()));
  vi.stubGlobal("fetch", fetch);
  const user = userEvent.setup();
  mount("/inspecoes?municipio=Recife&page=3");
  await screen.findByRole("button", { name: /Ajustar filtros/ });
  const trigger = screen.getByRole("button", { name: /Ajustar filtros/ });
  await user.click(trigger);
  const dialog = screen.getByRole("dialog", {
    name: "Ajustar filtros",
  });
  await user.selectOptions(
    within(dialog).getByLabelText("Município"),
    "Olinda",
  );
  await user.keyboard("{Escape}");
  await waitFor(() => expect(dialog).not.toBeVisible());
  expect(trigger).toHaveFocus();
  expect(screen.getByLabelText("URL atual")).toHaveTextContent(
    "municipio=Recife&page=3",
  );
  await user.click(trigger);
  expect(
    within(screen.getByRole("dialog")).getByLabelText("Município"),
  ).toHaveValue("Recife");
});

it("apresenta os cinco campos da fila e registros mobile sem faixa de prioridade inventada", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(respond(envelope())));
  mount();
  expect(
    await screen.findByRole("table", { name: /Suspeitas/ }),
  ).toBeInTheDocument();
  for (const heading of [
    "UC / prioridade",
    "Motivo da suspeita",
    "Indicador usado",
    "Energia estimada",
    "Ação",
  ]) {
    expect(
      screen.getByRole("columnheader", { name: heading }),
    ).toBeInTheDocument();
  }
  const mobileCard = screen.getByRole("article", { name: "Suspeita UC-1004" });
  expect(
    within(mobileCard).getByText("Lacuna de leitura e medidor retirado"),
  ).toBeVisible();
  expect(
    within(mobileCard).getByText("Lacuna de leitura · Medidor retirado"),
  ).toBeVisible();
  expect(screen.queryByText(/Alta|Média/)).not.toBeInTheDocument();
});

it("mostra carregamento, erro e nova tentativa sem apresentar a falha como fila vazia", async () => {
  let release: ((value: Response) => void) | undefined;
  const fetch = vi
    .fn()
    .mockImplementationOnce(
      () =>
        new Promise<Response>((resolve) => {
          release = resolve;
        }),
    )
    .mockImplementationOnce(() => respond(envelope()));
  vi.stubGlobal("fetch", fetch);
  mount();
  expect(screen.getByRole("status")).toHaveTextContent("Carregando fila");
  await waitFor(() => expect(release).toBeDefined());
  release!(respond({}, 503));
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Não foi possível consultar",
  );
  expect(screen.queryByText(/Nenhuma suspeita/)).not.toBeInTheDocument();
  await userEvent.click(
    screen.getByRole("button", { name: "Tentar novamente" }),
  );
  expect(await firstEvidenceLink()).toBeVisible();
});

it("avisa atualização em segundo plano e preserva a última consulta quando ela falha", async () => {
  let release: ((value: Response) => void) | undefined;
  const fetch = vi
    .fn()
    .mockResolvedValueOnce(respond(envelope()))
    .mockImplementationOnce(
      () =>
        new Promise<Response>((resolve) => {
          release = resolve;
        }),
    );
  vi.stubGlobal("fetch", fetch);
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  mount("/inspecoes", client);
  await firstEvidenceLink();
  void client.invalidateQueries();
  expect(
    await screen.findByText(
      "Atualizando evidências; exibindo a última consulta válida.",
    ),
  ).toBeVisible();
  expect(
    (
      await screen.findAllByRole("link", { name: "Ver evidência de UC-1004" })
    )[0],
  ).toBeVisible();
  await waitFor(() => expect(release).toBeDefined());
  release!(respond({}, 503));
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Exibindo a última consulta válida",
  );
  expect(
    (
      await screen.findAllByRole("link", { name: "Ver evidência de UC-1004" })
    )[0],
  ).toBeVisible();
});

it("aceita link direto e informa suspeita inexistente", async () => {
  const fetch = vi
    .fn()
    .mockImplementation((url: string) =>
      url.includes("/queue/UC-9999")
        ? respond({}, 404)
        : respond(envelope([item], 2, 1, 2)),
    );
  vi.stubGlobal("fetch", fetch);
  const user = userEvent.setup();
  mount("/inspecoes?municipio=Recife&page_size=1&page=2&uc=UC-9999");
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Suspeita não encontrada",
  );
  await user.click(screen.getByRole("link", { name: "Voltar à fila" }));
  expect(await firstEvidenceLink()).toBeVisible();
  expect(screen.getByLabelText("URL atual")).toHaveTextContent(
    "municipio=Recife&page_size=1&page=2",
  );
  expect(fetch.mock.calls[0][0]).toContain("/queue/UC-9999");
});

it("bloqueia parâmetros repetidos sem consultar a API", () => {
  const fetch = vi.fn();
  vi.stubGlobal("fetch", fetch);
  mount("/inspecoes?page=1&page=2");
  expect(screen.getByRole("alert")).toHaveTextContent(
    "Parâmetros de inspeção inválidos",
  );
  expect(fetch).not.toHaveBeenCalled();
});

it("rejeita contratos inválidos antes de apresentar métricas", () => {
  expect(() =>
    decodeQueue({
      ...envelope(),
      data: {
        ...envelope().data,
        summary: {
          total_units: 2,
          highest_priority: 0.92,
          estimated_units: 2,
          unavailable_estimate_units: 1,
        },
      },
    }),
  ).toThrow();
  expect(() =>
    decodeQueue({
      ...envelope(),
      data: { ...envelope().data, items: [{ ...item, priority: 92 }] },
    }),
  ).toThrow();
  expect(() =>
    decodeDetail({
      ...detail,
      data: {
        ...detail.data,
        estimate_evidence: {
          ...detail.data.estimate_evidence,
          horizon_months: 0,
        },
      },
    }),
  ).toThrow();
  expect(() =>
    decodeQueue({
      ...envelope(),
      pagination: { page: 1, page_size: 10, total: 2, total_pages: 9 },
    }),
  ).toThrow();
});
