import { beforeEach, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, useLocation } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import InspecoesPage from "./InspecoesPage";
import { DemoSessionProvider } from "@/shared/test/TestProviders";
import { decodeDetail, decodeQueue } from "./contract";
import {
  isGoldPublicationStale,
  resetGoldPublication,
} from "@/shared/analytics/goldPublication";

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
      <DemoSessionProvider>
        <MemoryRouter initialEntries={[url]}>
          <InspecoesPage />
          <Location />
        </MemoryRouter>
      </DemoSessionProvider>
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
  resetGoldPublication();
});

const goldMetadata = {
  contract_version: "2.0.0",
  status: "available",
  period: null,
  filters: { municipio: null, bairro: null, classe: null, alimentador: null },
  source: {
    kind: "gold",
    version: "gold-batch",
    is_demo: false,
    updated_at: "2026-10-29T12:00:00Z",
  },
  limitations: ["A fila é um snapshot cadastral."],
  temporal_scope: "snapshot",
  schema_version: "gold-csv-v2",
  fingerprint: "a".repeat(64),
};
const goldItem = {
  queue_position: 7,
  uc_id: "UC-GOLD",
  municipality: "Recife",
  neighborhood: null,
  class_name: "Residencial",
  feeder_id: null,
  category: "REVISAR",
  reason: "REVISAR",
  potential_recoverable_energy_kwh: null,
  recovery_unavailable_reason:
    "A Gold publicada não contém uma estimativa de energia recuperável.",
  evidence: {
    inspections_performed: 0,
    confirmed_irregular_inspections: null,
    historical_average_kwh_per_reading: null,
    distributed_generation_present: "Sim",
    cadastral_status: "ATIVA",
    call_center_contacts: null,
    interruptions: null,
    historical_recovery_mean_kwh_per_inspection: 20,
    historical_recovery_interval_lower_kwh: 5,
    historical_recovery_interval_upper_kwh: 40,
    historical_recovery_reference: "global",
    historical_recovery_status: "DISPONIVEL_REFERENCIA_HISTORICA",
  },
  variation: {
    p1_start: "2022-07",
    p1_end: "2023-06",
    p1_months_observed: 0,
    p1_average_kwh_per_month: null,
    p2_start: "2025-07",
    p2_end: "2026-06",
    p2_months_observed: 12,
    p2_average_kwh_per_month: 0,
    variation_kwh: null,
    variation_pct: null,
    drop_over_30_pct: null,
  },
};
const goldQueue = {
  data: {
    items: [goldItem],
    filter_options: {
      municipio: ["Recife"],
      bairro: [],
      classe: ["Residencial"],
      alimentador: [],
    },
    summary: {
      total_units: 1,
      categories: { REVISAR: 1 },
      uncategorized_units: 0,
      estimated_units: 0,
      unavailable_estimate_units: 1,
    },
  },
  pagination: { page: 1, page_size: 10, total: 1, total_pages: 1 },
  metadata: goldMetadata,
};
const goldDetail = {
  data: {
    ...goldItem,
    rule_version: "gold-fila-inspecao-v1",
    limitations: ["A categoria não é prioridade operacional."],
    investigation_potential: {
      baseline_start: "2023-11",
      baseline_end: "2024-01",
      recent_start: "2024-11",
      recent_end: "2025-01",
      baseline_kwh: 900,
      recent_kwh: 600,
      potential_kwh: 300,
      unavailable_reason: null,
    },
    consumption_comparison: {
      baseline_start: "2024-08",
      baseline_end: "2024-10",
      recent_start: "2024-11",
      recent_end: "2025-01",
      baseline_kwh: 300,
      recent_kwh: 150,
      change_percent: -50,
      unavailable_reason: null,
    },
  },
  metadata: goldMetadata,
};

it("restringe bairros ao município na fila Gold atual", async () => {
  const queue = {
    ...goldQueue,
    data: {
      ...goldQueue.data,
      filter_options: {
        ...goldQueue.data.filter_options,
        municipio: ["Recife", "Olinda"],
        bairro: ["Centro", "Bairro Novo"],
      },
      neighborhoods: [
        { municipio: "Recife", bairro: "Centro" },
        { municipio: "Olinda", bairro: "Bairro Novo" },
      ],
    },
  };
  vi.stubGlobal(
    "fetch",
    vi.fn().mockImplementation(async () => respond(queue)),
  );
  const user = userEvent.setup();
  mount("/inspecoes");
  await screen.findByRole("columnheader", {
    name: "Posição / UC / categoria",
  });
  await user.click(screen.getByRole("button", { name: "Ajustar filtros" }));
  expect(screen.getByLabelText("Bairro")).toBeDisabled();
  expect(
    screen.getByRole("option", {
      name: "Selecione um município primeiro",
    }),
  ).toBeInTheDocument();
  await user.selectOptions(screen.getByLabelText("Município"), "Olinda");
  expect(screen.getByLabelText("Bairro")).toBeEnabled();
  expect(
    screen.getByRole("option", { name: "Bairro Novo" }),
  ).toBeInTheDocument();
  expect(
    screen.queryByRole("option", { name: "Centro" }),
  ).not.toBeInTheDocument();
});

it("apresenta fila Gold sem score e cria ordem com lote e fingerprint confirmados", async () => {
  const createdOrder = {
    id: 58,
    uc_id: "UC-GOLD",
    reason: "REVISAR",
    priority: "MEDIA",
    status: "PENDENTE",
    notes: null,
    result: null,
    created_at: "2026-10-29T12:00:00Z",
    updated_at: "2026-10-29T12:00:00Z",
    suspicion_reference: "sha256:gold",
    version: 1,
    cancellation_reason: null,
  };
  const fetch = vi
    .fn()
    .mockImplementation((url: string, options?: RequestInit) => {
      if (options?.method === "POST")
        return Promise.resolve(respond(createdOrder, 201));
      return Promise.resolve(
        url.includes("/queue/UC-GOLD")
          ? respond(goldDetail)
          : respond(goldQueue),
      );
    });
  vi.stubGlobal("fetch", fetch);
  const user = userEvent.setup();
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  mount("/inspecoes", client);

  expect(
    await screen.findByRole("columnheader", {
      name: "Posição / UC / categoria",
    }),
  ).toBeVisible();
  expect(screen.getByText("UC-GOLD / REVISAR")).toBeVisible();
  expect(screen.getAllByText("Posição oficial na fila: 7")).toHaveLength(2);
  expect(
    screen.getAllByText(
      /Estimativas condicionais: 0 UCs disponíveis e 1 sem estimativa válida/,
    ),
  ).not.toHaveLength(0);
  expect(
    screen.getByRole("columnheader", { name: "Energia a recuperar" }),
  ).toBeVisible();
  expect(
    screen.queryByRole("columnheader", { name: "Evidências publicadas" }),
  ).not.toBeInTheDocument();
  expect(screen.queryByText("Evidências publicadas")).not.toBeInTheDocument();
  expect(
    screen.queryByText(/Contatos ao atendimento: indisponível/),
  ).not.toBeInTheDocument();
  expect(
    screen.queryByText(/Diferença observada não é estimativa/),
  ).not.toBeInTheDocument();
  expect(
    screen.queryByText("Prioridade demonstrativa"),
  ).not.toBeInTheDocument();
  expect(screen.getByLabelText("Ordenar por")).toHaveValue(
    "queue_position:asc",
  );
  expect(screen.queryByLabelText("Direção da ordenação")).toBeNull();
  expect(
    screen.getByRole("columnheader", { name: "Posição / UC / categoria" }),
  ).toHaveAttribute("aria-sort", "ascending");
  expect(
    screen.getByRole("columnheader", { name: "Energia a recuperar" }),
  ).toHaveAttribute("aria-sort", "none");
  await user.click(screen.getByRole("button", { name: "Ajustar filtros" }));
  const filterDialog = screen.getByRole("dialog", { name: "Ajustar filtros" });
  expect(within(filterDialog).getByLabelText("Município")).toBeVisible();
  expect(within(filterDialog).getByLabelText("Bairro")).toBeVisible();
  expect(within(filterDialog).getByLabelText("Classe")).toBeVisible();
  expect(within(filterDialog).getByLabelText("Alimentador")).toBeVisible();
  expect(within(filterDialog).queryByLabelText("Ordenar por")).toBeNull();
  expect(within(filterDialog).queryByLabelText("Por página")).toBeNull();
  expect(
    within(filterDialog).queryByRole("option", {
      name: "Posição oficial da fila",
    }),
  ).not.toBeInTheDocument();
  await user.keyboard("{Escape}");
  await user.click(
    screen.getAllByRole("link", { name: "Ver evidência de UC-GOLD" })[0],
  );
  expect(
    await screen.findByRole("region", {
      name: "Energia a recuperar (estimativa)",
    }),
  ).toHaveTextContent("Estimativa indisponível");
  expect(
    screen.getByText(/fotografia cadastral, sem competência mensal/),
  ).toBeVisible();
  await user.click(screen.getByText("Potencial estimado para investigação"));
  await user.click(screen.getByText("Referência histórica de recuperação"));
  await user.click(screen.getByText("Comparação proposta de consumo"));
  expect(
    screen.getByRole("region", {
      name: "Potencial estimado para investigação",
    }),
  ).toHaveTextContent("300 kWh");
  expect(
    screen.getByText(/geração distribuída cadastrada; ela pode influenciar/),
  ).toBeVisible();
  expect(
    screen.getByText(/Não é energia recuperada, previsão validada/),
  ).toBeVisible();
  expect(
    screen.getByRole("region", { name: "Referência histórica de recuperação" }),
  ).toHaveTextContent("não é estimativa para esta UC");
  expect(
    screen.getByRole("region", { name: "Comparação proposta de consumo" }),
  ).toHaveTextContent("-50%");
  await user.click(
    screen.getByRole("button", { name: "Criar ordem de inspeção" }),
  );
  expect(await screen.findByRole("status")).toHaveTextContent(
    "Ordem 58 confirmada pelo servidor",
  );
  const post = fetch.mock.calls.find(
    ([, options]) => options?.method === "POST",
  );
  const analyticGets = fetch.mock.calls.filter(
    ([url, options]) =>
      options?.method !== "POST" && String(url).includes("/queue/UC-GOLD"),
  );
  expect(analyticGets.length).toBeGreaterThan(0);
  for (const [url] of analyticGets) {
    const request = new URL(String(url), window.location.origin);
    expect(request.searchParams.has("expected_lote")).toBe(true);
    expect(request.searchParams.has("expected_fingerprint")).toBe(true);
  }
  expect(JSON.parse(post?.[1]?.body as string)).toMatchObject({
    source_version: "gold-batch",
    source_fingerprint: "a".repeat(64),
    rule_version: "gold-fila-inspecao-v1",
  });
});

it("oferece ordenar a fila Gold pela energia recuperável estimada", async () => {
  const fetch = vi.fn().mockImplementation(() => respond(goldQueue));
  vi.stubGlobal("fetch", fetch);
  const user = userEvent.setup();
  mount("/inspecoes");

  const ordering = await screen.findByLabelText("Ordenar por");
  expect(
    within(ordering).getByRole("option", {
      name: "Energia recuperável estimada (decrescente)",
    }),
  ).toBeEnabled();
  await user.selectOptions(ordering, "potential_recoverable_energy_kwh:desc");
  await waitFor(() =>
    expect(screen.getByLabelText("URL atual")).toHaveTextContent(
      "order_by=potential_recoverable_energy_kwh&direction=desc",
    ),
  );
  await waitFor(() =>
    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining("order_by=potential_recoverable_energy_kwh"),
      expect.anything(),
    ),
  );
});

it("exige nova confirmação após troca de fingerprint e não repete a intenção obsoleta", async () => {
  const nextMetadata = {
    ...goldMetadata,
    source: { ...goldMetadata.source, version: "gold-batch-2" },
    fingerprint: "b".repeat(64),
  };
  let detailReads = 0;
  let writes = 0;
  const keys: string[] = [];
  const fetch = vi
    .fn()
    .mockImplementation((url: string, options?: RequestInit) => {
      if (options?.method === "POST") {
        writes += 1;
        const headers = new Headers(options.headers);
        keys.push(headers.get("Idempotency-Key") ?? "");
        return Promise.resolve(
          writes === 1
            ? respond(
                {
                  detail: "A publicação mudou.",
                  error: { code: "stale_suspicion" },
                },
                409,
              )
            : respond(
                {
                  id: 59,
                  uc_id: "UC-GOLD",
                  reason: "REVISAR",
                  priority: "MEDIA",
                  status: "PENDENTE",
                  notes: null,
                  result: null,
                  created_at: "2026-10-29T12:00:00Z",
                  updated_at: "2026-10-29T12:00:00Z",
                  suspicion_reference: "sha256:gold",
                  version: 1,
                  cancellation_reason: null,
                },
                201,
              ),
        );
      }
      if (url.includes("/queue/UC-GOLD")) {
        detailReads += 1;
        return Promise.resolve(
          respond({
            ...goldDetail,
            metadata: detailReads === 1 ? goldMetadata : nextMetadata,
          }),
        );
      }
      return Promise.resolve(respond({ ...goldQueue, metadata: goldMetadata }));
    });
  vi.stubGlobal("fetch", fetch);
  const user = userEvent.setup();
  const staleClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  mount("/inspecoes", staleClient);
  await user.click(
    (
      await screen.findAllByRole("link", { name: "Ver evidência de UC-GOLD" })
    )[0],
  );
  await user.click(
    await screen.findByRole("button", { name: "Criar ordem de inspeção" }),
  );
  await screen.findByText(/A suspeita mudou desde a consulta/);
  await user.click(
    screen.getByRole("button", { name: "Atualizar dados da suspeita" }),
  );
  await waitFor(() => expect(isGoldPublicationStale()).toBe(true));
  const analyticQueries = {
    predicate: (query: { queryKey: readonly unknown[] }) =>
      ["inspection-queue", "inspection-suspicion"].includes(
        String(query.queryKey[0]),
      ),
  };
  await staleClient.cancelQueries(analyticQueries);
  resetGoldPublication();
  await staleClient.resetQueries(analyticQueries);
  await waitFor(() => expect(detailReads).toBeGreaterThan(2));
  expect(writes).toBe(1);
  expect(
    await screen.findByRole("button", {
      name: "Confirmar com evidência atual",
    }),
  ).toBeEnabled();
  expect(writes).toBe(1);
  await user.click(
    screen.getByRole("button", { name: "Confirmar com evidência atual" }),
  );
  await screen.findByText(/Ordem 59 confirmada pelo servidor/);
  expect(writes).toBe(2);
  expect(keys[0]).not.toBe(keys[1]);
  const postBodies = fetch.mock.calls
    .filter(([, options]) => options?.method === "POST")
    .map(([, options]) => JSON.parse(String(options?.body)));
  expect(postBodies[0]).toMatchObject({
    source_version: "gold-batch",
    source_fingerprint: "a".repeat(64),
  });
  expect(postBodies[1]).toMatchObject({
    source_version: "gold-batch-2",
    source_fingerprint: "b".repeat(64),
  });
});

it("explica a janela da fila sem expor identificadores técnicos", async () => {
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
  expect(
    await screen.findByText(/A fila não informa uma janela temporal própria/),
  ).toBeVisible();
  expect(screen.queryByText("GOLD-ARTIFICIAL:hash")).not.toBeInTheDocument();
  expect(
    screen.queryByRole("region", {
      name: "Período, unidades e fonte dos dados",
    }),
  ).not.toBeInTheDocument();
});

it("mostra a estimativa condicional e sua faixa na fila e no detalhe Gold", async () => {
  const candidate = {
    ...goldItem,
    potential_recoverable_energy_kwh: 125.5,
    recovery_unavailable_reason: null,
    evidence: {
      ...goldItem.evidence,
      estimated_recoverable_energy_kwh: 125.5,
      recovery_interval_lower_kwh: 100,
      recovery_interval_upper_kwh: 151,
      recovery_estimate_status: "ESTIMATIVA_UC_POR_CONSUMO_SE_CONFIRMADA",
      recovery_estimate_method: "CONSUMO_CONDICIONAL_V1",
      recovery_estimate_confidence_level: 0.9,
      recovery_estimate_window_anchor: "2026-06",
      recovery_estimate_window_months: 12,
      recovery_estimate_minimum_window_months: 6,
    },
  };
  const queue = {
    ...goldQueue,
    data: {
      ...goldQueue.data,
      items: [candidate],
      summary: {
        ...goldQueue.data.summary,
        estimated_units: 1,
        unavailable_estimate_units: 0,
      },
    },
  };
  const detail = {
    ...goldDetail,
    data: { ...goldDetail.data, ...candidate },
  };
  vi.stubGlobal(
    "fetch",
    vi
      .fn()
      .mockImplementation((url: string) =>
        Promise.resolve(
          url.includes("/queue/UC-GOLD") ? respond(detail) : respond(queue),
        ),
      ),
  );
  const user = userEvent.setup();
  mount("/inspecoes");

  expect(await screen.findAllByText("125,5 kWh")).not.toHaveLength(0);
  expect(
    screen.getAllByText(/Faixa nominal de 90%: 100 kWh a 151 kWh/),
  ).not.toHaveLength(0);
  expect(
    screen.getAllByText(/1 UCs disponíveis e 0 sem estimativa válida/),
  ).not.toHaveLength(0);
  await user.click(
    (
      await screen.findAllByRole("link", { name: "Ver evidência de UC-GOLD" })
    )[0],
  );
  expect(
    await screen.findByRole("region", {
      name: "Energia a recuperar (estimativa)",
    }),
  ).toHaveTextContent("125,5 kWh");
  expect(
    screen.getByText(
      "Estimativa se a irregularidade se confirmar; não garante recuperação nesta UC.",
    ),
  ).toBeVisible();
  expect(
    screen.getByText(/A faixa foi validada temporalmente/),
  ).toHaveTextContent(/Faixa nominal de 90%: 100 kWh a 151 kWh/);
  expect(
    screen.getByText(
      /Janela de aplicação: 12 meses até junho de 2026 \(mínimo: 6 meses\)/,
    ),
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
      publication_lote: "artificial",
      publication_fingerprint: "a".repeat(64),
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
  expect(
    screen.getByText(
      /A fonte não fornece estimativa individual de energia recuperável/,
    ),
  ).toBeVisible();
  expect(screen.queryByText("Estimativa indisponível")).not.toBeInTheDocument();
  expect(screen.getAllByText("Histórico confirmado").length).toBeGreaterThan(0);
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
  await user.click(
    screen.getByText("Média histórica de recuperação por inspeção"),
  );
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
  expect(
    await screen.findByRole("button", { name: "Página 2" }),
  ).toHaveAttribute("aria-current", "page");
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
    await screen.findByRole("button", {
      name: "Confirmar com evidência atual",
    }),
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
  expect(screen.queryByText("Competência")).not.toBeInTheDocument();
  expect(screen.queryByText("Comparar com")).not.toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Energia estimada" }));
  await user.click(screen.getByRole("button", { name: "UC / prioridade" }));
  await user.click(screen.getByRole("button", { name: "UC / prioridade" }));
  const pagination = () =>
    within(screen.getByRole("navigation", { name: "Paginação da fila" }));
  await user.selectOptions(pagination().getByLabelText("Por página"), "20");
  await user.selectOptions(pagination().getByLabelText("Por página"), "50");
  await user.click(screen.getByRole("button", { name: "Ajustar filtros" }));
  await user.selectOptions(screen.getByLabelText("Município"), "Olinda");
  await user.click(screen.getByRole("button", { name: "Aplicar filtros" }));
  expect(
    await screen.findByText(
      "Nenhuma suspeita neste recorte. Isso não comprova ausência de perdas.",
    ),
  ).toBeVisible();
  const url = new URL(fetch.mock.calls.at(-1)![0], window.location.origin);
  expect(url.searchParams.get("municipio")).toBe("Olinda");
  expect(url.searchParams.get("order_by")).toBe("priority");
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

  expect(
    await within(
      screen.getByRole("region", { name: "Filtros aplicados" }),
    ).findByText("AL-03"),
  ).toBeVisible();
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
  expect(screen.getByLabelText("URL atual")).toHaveTextContent(
    "alimentador=AL-03",
  );
  await user.click(screen.getByRole("button", { name: "Aplicar filtros" }));
  await waitFor(() => {
    expect(screen.getByLabelText("URL atual")).not.toHaveTextContent(
      "alimentador=",
    );
  });
  expect(
    within(
      screen.getByRole("region", { name: "Filtros aplicados" }),
    ).queryByText("AL-03"),
  ).not.toBeInTheDocument();
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
  await user.click(await screen.findByRole("button", { name: "Página 2" }));
  await waitFor(() =>
    expect(screen.getByRole("button", { name: "Página 2" })).toHaveAttribute(
      "aria-current",
      "page",
    ),
  );
  expect(screen.getAllByText("Estimativa indisponível")).toHaveLength(2);
  expect(
    screen.queryByRole("region", { name: "Resumo do recorte da fila" }),
  ).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Ver fundamentos" })).toBeVisible();
  expect(
    screen.queryByRole("button", { name: "Página 3" }),
  ).not.toBeInTheDocument();
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

it("apresenta os quatro campos da fila e registros mobile sem faixa de prioridade inventada", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(respond(envelope())));
  mount();
  expect(
    await screen.findByRole("table", { name: /Suspeitas/ }),
  ).toBeInTheDocument();
  for (const heading of [
    "UC / prioridade",
    "Motivo da suspeita",
    "Energia estimada",
    "Ação",
  ]) {
    expect(
      screen.getByRole("columnheader", { name: heading }),
    ).toBeInTheDocument();
  }
  expect(
    screen.queryByRole("columnheader", { name: "Indicador usado" }),
  ).not.toBeInTheDocument();
  const mobileCard = screen.getByRole("article", { name: "Suspeita UC-1004" });
  expect(
    within(mobileCard).getByText("Lacuna de leitura e medidor retirado"),
  ).toBeVisible();
  expect(within(mobileCard).queryByText("Indicador usado")).toBeNull();
  expect(
    within(mobileCard).queryByText("Lacuna de leitura · Medidor retirado"),
  ).toBeNull();
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

it("uses descending as the default direction for Gold recovery estimates", async () => {
  const fetch = vi.fn(async (_url: string) => respond(goldQueue));
  vi.stubGlobal("fetch", fetch);
  mount("/inspecoes?order_by=potential_recoverable_energy_kwh");

  expect(await screen.findByLabelText("Ordenar por")).toBeVisible();
  expect(screen.getByLabelText("Ordenar por")).toHaveValue(
    "potential_recoverable_energy_kwh:desc",
  );
  expect(
    screen.getByRole("columnheader", { name: "Energia a recuperar" }),
  ).toHaveAttribute("aria-sort", "descending");

  const request = new URL(fetch.mock.calls.at(-1)![0], window.location.origin);
  expect(request.searchParams.get("order_by")).toBe(
    "potential_recoverable_energy_kwh",
  );
  expect(request.searchParams.get("direction")).toBeNull();
});

it("ordena a fila de demonstração pelo cabeçalho, voltando à página 1", async () => {
  const fetch = vi.fn(async (_url: string) =>
    respond(envelope([item, second], 3, 10, 30)),
  );
  vi.stubGlobal("fetch", fetch);
  const user = userEvent.setup();
  mount("/inspecoes?page=3");

  const priority = await screen.findByRole("columnheader", {
    name: "UC / prioridade",
  });
  const energyHeader = screen.getByRole("columnheader", {
    name: "Energia estimada",
  });
  expect(priority).toHaveAttribute("aria-sort", "descending");
  expect(energyHeader).toHaveAttribute("aria-sort", "none");
  expect(
    screen.queryByRole("button", { name: "Motivo da suspeita" }),
  ).not.toBeInTheDocument();

  await user.click(screen.getByRole("button", { name: "Energia estimada" }));
  await waitFor(() =>
    expect(screen.getByLabelText("URL atual")).toHaveTextContent(
      "page=1&order_by=potential_recoverable_energy_kwh&direction=desc",
    ),
  );
  await waitFor(() =>
    expect(
      screen.getByRole("columnheader", { name: "Energia estimada" }),
    ).toHaveAttribute("aria-sort", "descending"),
  );
  await user.click(screen.getByRole("button", { name: "Energia estimada" }));
  await waitFor(() =>
    expect(screen.getByLabelText("URL atual")).toHaveTextContent(
      "direction=asc",
    ),
  );
  await waitFor(() =>
    expect(
      screen.getByRole("columnheader", { name: "Energia estimada" }),
    ).toHaveAttribute("aria-sort", "ascending"),
  );
  await user.click(screen.getByRole("button", { name: "UC / prioridade" }));
  await waitFor(() => {
    const request = new URL(
      fetch.mock.calls.at(-1)![0],
      window.location.origin,
    );
    expect(request.searchParams.get("order_by")).toBe("priority");
    expect(request.searchParams.get("direction")).toBe("desc");
    expect(request.searchParams.get("page")).toBe("1");
  });
});

it("ordena a fila Gold com a posição mais promissora primeiro e alterna a direção", async () => {
  const fetch = vi.fn(async (_url: string) => respond(goldQueue));
  vi.stubGlobal("fetch", fetch);
  const user = userEvent.setup();
  mount("/inspecoes");

  const position = await screen.findByRole("button", {
    name: "Posição / UC / categoria",
  });
  await user.click(position);
  await waitFor(() =>
    expect(screen.getByLabelText("URL atual")).toHaveTextContent(
      "order_by=queue_position&direction=desc",
    ),
  );
  await user.click(
    await screen.findByRole("button", { name: "Energia a recuperar" }),
  );
  await waitFor(() =>
    expect(screen.getByLabelText("URL atual")).toHaveTextContent(
      "order_by=potential_recoverable_energy_kwh&direction=desc",
    ),
  );
  await user.click(
    await screen.findByRole("button", { name: "Posição / UC / categoria" }),
  );
  await waitFor(() =>
    expect(screen.getByLabelText("URL atual")).toHaveTextContent(
      "order_by=queue_position&direction=asc",
    ),
  );
});

it.each([
  ["uc_id", "asc", "Número da UC (crescente)"],
  ["category", "desc", "Categoria (decrescente)"],
])(
  "mantém links com order_by=%s sem cabeçalho ativo",
  async (order, direction, option) => {
    const fetch = vi.fn(async (_url: string) => respond(goldQueue));
    vi.stubGlobal("fetch", fetch);
    mount(`/inspecoes?order_by=${order}&direction=${direction}`);

    const header = await screen.findByRole("columnheader", {
      name: "Posição / UC / categoria",
    });
    expect(header).toHaveAttribute("aria-sort", "none");
    expect(
      screen.getByRole("columnheader", { name: "Energia a recuperar" }),
    ).toHaveAttribute("aria-sort", "none");
    expect(screen.getByLabelText("Ordenar por")).toHaveValue(
      `${order}:${direction}`,
    );
    expect(screen.getByRole("option", { name: option })).toBeInTheDocument();
    const request = new URL(
      fetch.mock.calls.at(-1)![0],
      window.location.origin,
    );
    expect(request.searchParams.get("order_by")).toBe(order);
    expect(request.searchParams.get("direction")).toBe(direction);
  },
);

function sizeOptions(select: HTMLElement) {
  return within(select)
    .getAllByRole("option")
    .map((option) => option.textContent);
}

const pageSizeLayouts = [
  ["Gold", () => respond(goldQueue)],
  ["demonstração", () => respond(envelope())],
] as const;

it.each(pageSizeLayouts)(
  "pede 5 UCs por padrão e oferece 5, 10, 20 e 50 na fila %s",
  async (_layout, reply) => {
    const fetch = vi.fn(async (_url: string) => reply());
    vi.stubGlobal("fetch", fetch);
    mount("/inspecoes");

    const footer = await screen.findByRole("navigation", {
      name: "Paginação da fila",
    });
    const request = new URL(
      fetch.mock.calls.at(-1)![0],
      window.location.origin,
    );
    expect(request.searchParams.get("page_size")).toBe("5");
    const controls = screen.getByLabelText("Controles da fila");
    for (const select of [within(footer).getByLabelText("Por página")]) {
      expect(select).toHaveValue("5");
      expect(sizeOptions(select)).toEqual(["5", "10", "20", "50"]);
    }
    expect(within(controls).getByLabelText("Ordenar por")).toBeInTheDocument();
    expect(screen.queryByLabelText("UCs por página")).toBeNull();
  },
);

it.each(pageSizeLayouts)(
  "volta à página 1 ao mudar Por página na fila %s",
  async (_layout, reply) => {
    const fetch = vi.fn(async (_url: string) => reply());
    vi.stubGlobal("fetch", fetch);
    const user = userEvent.setup();
    mount("/inspecoes?page=3");

    const footer = await screen.findByRole("navigation", {
      name: "Paginação da fila",
    });
    await user.selectOptions(within(footer).getByLabelText("Por página"), "20");
    await waitFor(() => {
      const request = new URL(
        fetch.mock.calls.at(-1)![0],
        window.location.origin,
      );
      expect(request.searchParams.get("page_size")).toBe("20");
      expect(request.searchParams.get("page")).toBe("1");
    });
  },
);

it.each([
  ["10", ["5", "10", "20", "50"]],
  ["100", ["5", "10", "20", "50", "100"]],
  ["1", ["1", "5", "10", "20", "50"]],
])(
  "mantém links antigos com page_size=%s e só acrescenta a opção se faltar",
  async (size, options) => {
    const fetch = vi.fn(async (_url: string) => respond(envelope()));
    vi.stubGlobal("fetch", fetch);
    mount(`/inspecoes?page_size=${size}`);

    const footer = await screen.findByRole("navigation", {
      name: "Paginação da fila",
    });
    const select = within(footer).getByLabelText("Por página");
    expect(select).toHaveValue(size);
    expect(sizeOptions(select)).toEqual(options);
    const request = new URL(
      fetch.mock.calls.at(-1)![0],
      window.location.origin,
    );
    expect(request.searchParams.get("page_size")).toBe(size);
  },
);

it("mostra só o botão de exportar entre o aviso e a tabela da fila", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => respond(envelope())),
  );
  mount("/inspecoes");

  const table = await screen.findByRole("table", { name: /Suspeitas/ });
  const notice = screen.getByRole("complementary", {
    name: "Prioridade demonstrativa",
  });
  const button = screen.getByRole("button", { name: "Exportar fila" });
  const follows = (first: Element, second: Element) =>
    first.compareDocumentPosition(second) & Node.DOCUMENT_POSITION_FOLLOWING;
  expect(follows(notice, button)).toBeTruthy();
  expect(follows(button, table)).toBeTruthy();
  expect(screen.queryByText("Enviar a fila para a equipe")).toBeNull();
  expect(screen.queryByText(/Prepare a fila de inspeção/)).toBeNull();
});

it("mantém o botão de exportar antes da tabela na fila Gold", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => respond(goldQueue)),
  );
  mount("/inspecoes");

  const header = await screen.findByRole("columnheader", {
    name: "Posição / UC / categoria",
  });
  const button = screen.getByRole("button", { name: "Exportar fila" });
  expect(
    button.compareDocumentPosition(header) & Node.DOCUMENT_POSITION_FOLLOWING,
  ).toBeTruthy();
});

const INFO_NAME = "Como a prioridade é calculada";

it("abre a regra pelo ícone sem ordenar e fecha com Esc e ao clicar fora", async () => {
  const fetch = vi.fn(async (_url: string) => respond(envelope()));
  vi.stubGlobal("fetch", fetch);
  const user = userEvent.setup();
  mount("/inspecoes");

  const info = await screen.findByRole("button", { name: INFO_NAME });
  const calls = fetch.mock.calls.length;
  const url = screen.getByLabelText("URL atual").textContent;
  expect(screen.queryByRole("tooltip")).toBeNull();
  expect(info).toHaveAccessibleDescription(
    /Pontuação de priorização da fila; não é probabilidade de irregularidade/,
  );

  await user.click(info);
  expect(screen.getByRole("tooltip")).toHaveTextContent(
    "Soma dos pesos dos sinais presentes, limitada a 1 e arredondada a duas casas.",
  );
  expect(info).toHaveAttribute("aria-expanded", "true");
  expect(screen.getByLabelText("URL atual").textContent).toBe(url);
  expect(fetch.mock.calls.length).toBe(calls);
  expect(
    screen.getByRole("columnheader", { name: "UC / prioridade" }),
  ).toHaveAttribute("aria-sort", "descending");

  await user.keyboard("{Escape}");
  expect(screen.queryByRole("tooltip")).toBeNull();
  await user.click(info);
  await user.click(screen.getByRole("heading", { level: 1 }));
  expect(screen.queryByRole("tooltip")).toBeNull();
  await user.click(info);
  await user.click(info);
  expect(screen.queryByRole("tooltip")).toBeNull();
});

it("abre a regra ao focar pelo teclado e fecha ao sair do botão", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => respond(envelope())),
  );
  const user = userEvent.setup();
  mount("/inspecoes");

  const sort = await screen.findByRole("button", { name: "UC / prioridade" });
  sort.focus();
  await user.tab();
  expect(screen.getByRole("button", { name: INFO_NAME })).toHaveFocus();
  expect(screen.getByRole("tooltip")).toBeInTheDocument();
  await user.tab();
  expect(screen.queryByRole("tooltip")).toBeNull();
});

it("explica a fila Gold pela regra publicada, sem falar em pontuação", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => respond(goldQueue)),
  );
  const user = userEvent.setup();
  mount("/inspecoes");

  await user.click(await screen.findByRole("button", { name: INFO_NAME }));
  const rule = screen.getByRole("tooltip");
  expect(rule).toHaveTextContent(/É ordem de triagem/);
  expect(rule).not.toHaveTextContent(/Pontuação/);
  expect(
    screen.getByRole("columnheader", { name: "Posição / UC / categoria" }),
  ).toHaveAttribute("aria-sort", "ascending");
});

it("informa que a fonte publicada não fornece pesos", async () => {
  const published = envelope();
  vi.stubGlobal(
    "fetch",
    vi.fn(async () =>
      respond({
        ...published,
        metadata: {
          ...metadata,
          source: { ...metadata.source, kind: "gold_csv", is_demo: false },
        },
      }),
    ),
  );
  const user = userEvent.setup();
  mount("/inspecoes");

  await user.click(await screen.findByRole("button", { name: INFO_NAME }));
  expect(screen.getByRole("tooltip")).toHaveTextContent(
    "Categoria publicada na Gold. Não há score nem pesos fornecidos nesta versão.",
  );
});

it("resume o aviso da demonstração e tira da linha só o que ele já diz", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => respond(envelope())),
  );
  mount("/inspecoes");

  expect(
    await screen.findByText(
      "Dados sintéticos; priorização final e energia recuperável dependem de validação com as fontes.",
    ),
  ).toBeVisible();
  const line = screen.getByText(/atualização ilustrativa/);
  expect(line).toHaveTextContent(
    "Demonstração · atualização ilustrativa: 21/10/2026 · cobertura parcial",
  );
  expect(screen.queryByText(/Motivos e estimativas/)).toBeNull();
});

it("mantém dados sintéticos na linha do detalhe, onde não há aviso", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => respond(detail)),
  );
  mount("/inspecoes?uc=UC-1004");

  expect(await screen.findByText(/atualização ilustrativa/)).toHaveTextContent(
    "Demonstração · dados sintéticos · atualização ilustrativa: 21/10/2026 · cobertura parcial",
  );
});

function recoveryBlock() {
  return screen.getByRole("region", {
    name: "Energia a recuperar (estimativa)",
  });
}

function expectBefore(first: Element, second: Element) {
  expect(
    first.compareDocumentPosition(second) & Node.DOCUMENT_POSITION_FOLLOWING,
  ).toBeTruthy();
}

it("destaca a energia da demonstração acima do motivo, com o aviso junto ao valor", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => respond(detail)),
  );
  mount("/inspecoes?uc=UC-1004");

  const heading = await screen.findByRole("heading", {
    name: "O que motivou a investigação",
  });
  const block = recoveryBlock();
  expectBefore(block, heading);
  expect(within(block).getByText("45 kWh")).toHaveClass("text-4xl");
  expect(
    within(block).getByText(
      "Estimativa demonstrativa, sem confirmação de recuperação.",
    ),
  ).toBeVisible();
  expect(screen.getAllByText("45 kWh")).toHaveLength(1);
  expect(screen.queryByText("Energia potencialmente recuperável")).toBeNull();
  expect(screen.getByLabelText("Limite da evidência")).toBeVisible();
  expect(
    screen.getByRole("button", { name: "Criar ordem de inspeção" }),
  ).toBeInTheDocument();
});

it("na demonstração sem valor mantém o aviso e mostra a razão da indisponibilidade", async () => {
  const unavailable = (reason: string | null) => ({
    ...detail,
    data: {
      ...detail.data,
      potential_recoverable_energy_kwh: null,
      estimate_evidence: {
        ...detail.data.estimate_evidence,
        unavailable_reason: reason,
      },
    },
  });
  const fetch = vi.fn(async () =>
    respond(unavailable("Sem leitura comparável.")),
  );
  vi.stubGlobal("fetch", fetch);
  mount("/inspecoes?uc=UC-1004");

  await screen.findByRole("heading", { name: "O que motivou a investigação" });
  const block = recoveryBlock();
  expect(within(block).getByText("Estimativa indisponível")).toHaveClass(
    "text-2xl",
  );
  expect(block).not.toHaveTextContent(/\d/);
  expect(
    within(block).getByText(
      "Estimativa demonstrativa, sem confirmação de recuperação.",
    ),
  ).toBeVisible();
  expect(within(block).getByText("Sem leitura comparável.")).toBeVisible();
});

it("usa Insumos indisponíveis quando a demonstração não informa a razão", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () =>
      respond({
        ...detail,
        data: {
          ...detail.data,
          potential_recoverable_energy_kwh: null,
          estimate_evidence: {
            ...detail.data.estimate_evidence,
            unavailable_reason: null,
          },
        },
      }),
    ),
  );
  mount("/inspecoes?uc=UC-1004");

  await screen.findByRole("heading", { name: "O que motivou a investigação" });
  expect(
    within(recoveryBlock()).getByText("Insumos indisponíveis"),
  ).toBeVisible();
});

it("na fonte publicada sem estimativa mantém a informação de valor não fornecido", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () =>
      respond({
        ...detail,
        data: { ...detail.data, potential_recoverable_energy_kwh: null },
        metadata: {
          ...metadata,
          source: { ...metadata.source, kind: "gold_csv", is_demo: false },
        },
      }),
    ),
  );
  mount("/inspecoes?uc=UC-1004");

  await screen.findByRole("heading", { name: "O que motivou a investigação" });
  const block = recoveryBlock();
  expect(block).toHaveTextContent("Estimativa indisponível");
  expect(block).toHaveTextContent("Estimativa não fornecida nesta consulta.");
});

it("no Gold sem estimativa mostra o bloco acima da triagem, com a razão publicada", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => respond(goldDetail)),
  );
  mount("/inspecoes?uc=UC-GOLD");

  const heading = await screen.findByRole("heading", {
    name: "O que consta na triagem",
  });
  const block = recoveryBlock();
  expectBefore(block, heading);
  expect(within(block).getByText("Estimativa indisponível")).toHaveClass(
    "text-2xl",
  );
  expect(block).toHaveTextContent(
    "A Gold publicada não contém uma estimativa de energia recuperável.",
  );
  expect(screen.queryByText("Energia recuperável indisponível")).toBeNull();
  expect(screen.getByLabelText("Limite da evidência")).toBeVisible();
});

const GUIDANCE_TEXT =
  "Verificar cadastro, medição, histórico e eventual geração própria antes de concluir.";

function collapsedSummaries() {
  const details = [...document.querySelectorAll("article details")];
  expect(details.every((item) => !item.hasAttribute("open"))).toBe(true);
  return details.map((item) => item.querySelector("summary")?.textContent);
}

it("mostra Estimativa indisponível como texto neutro, sem parecer um valor", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => respond(goldDetail)),
  );
  mount("/inspecoes?uc=UC-GOLD");

  await screen.findByRole("heading", { name: "O que consta na triagem" });
  const text = within(recoveryBlock()).getByText("Estimativa indisponível");
  expect(text).toHaveClass("text-2xl", "text-content");
  expect(text).not.toHaveClass("text-4xl");
  expect(text).not.toHaveClass("text-brand");
});

it("mantém o valor em destaque quando há número", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => respond(detail)),
  );
  mount("/inspecoes?uc=UC-1004");

  await screen.findByRole("heading", { name: "O que motivou a investigação" });
  expect(within(recoveryBlock()).getByText("45 kWh")).toHaveClass(
    "text-4xl",
    "text-brand",
  );
});

it("no Gold recolhe a fundamentação e mantém evidências, orientação e limite visíveis", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => respond(goldDetail)),
  );
  const user = userEvent.setup();
  mount("/inspecoes?uc=UC-GOLD");

  await screen.findByRole("heading", { name: "O que consta na triagem" });
  expect(collapsedSummaries()).toEqual([
    "Referência histórica de recuperação",
    "Potencial estimado para investigação",
    "Comparação proposta de consumo",
    "Variação de consumo observada",
  ]);
  expect(screen.getByText("Motivo registrado")).toBeVisible();
  expect(screen.getByText("Evidências publicadas")).toBeVisible();
  expect(screen.getByText("Inspeções realizadas")).toBeVisible();
  expect(screen.getByText(GUIDANCE_TEXT)).toBeVisible();
  expect(screen.getByLabelText("Limite da evidência")).toBeVisible();
  expect(
    screen.getByText(/fotografia cadastral, sem competência mensal/),
  ).toBeVisible();
  expect(screen.getByText(/Não é energia recuperada/)).not.toBeVisible();

  await user.click(screen.getByText("Potencial estimado para investigação"));
  expect(screen.getByText(/Não é energia recuperada/)).toBeVisible();
  await user.click(screen.getByText("Potencial estimado para investigação"));
  expect(screen.getByText(/Não é energia recuperada/)).not.toBeVisible();
});

it("na demonstração mantém o chip e o aviso visíveis e recolhe a explicação e a janela", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => respond(detail)),
  );
  const user = userEvent.setup();
  mount("/inspecoes?uc=UC-1004");

  await screen.findByRole("heading", { name: "O que motivou a investigação" });
  expect(collapsedSummaries()).toEqual([
    "Como a prioridade é calculada",
    "Janela da evidência",
  ]);
  expect(
    screen.getByLabelText("Prioridade analítica: 0,92 de 1"),
  ).toBeVisible();
  expect(
    screen.getByText("Não é probabilidade de irregularidade."),
  ).toBeVisible();
  expect(screen.getByText("Motivo da suspeita")).toBeVisible();
  expect(screen.getByText("Sinais observados")).toBeVisible();
  expect(screen.getByText(GUIDANCE_TEXT)).toBeVisible();
  expect(screen.getByLabelText("Limite da evidência")).toBeVisible();

  const explanation = screen.getByText(/Pontuação de priorização da fila/);
  const period = screen.getByText("janeiro de 2025 a fevereiro de 2025");
  expect(explanation).not.toBeVisible();
  expect(period).not.toBeVisible();
  await user.click(screen.getByText("Como a prioridade é calculada"));
  expect(explanation).toBeVisible();
  await user.click(screen.getByText("Janela da evidência"));
  expect(period).toBeVisible();
});

it("na fonte publicada deixa visível o que limita a evidência", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () =>
      respond({
        ...detail,
        data: {
          ...detail.data,
          priority: null,
          priority_label: "ALTA",
          potential_recoverable_energy_kwh: null,
        },
        metadata: {
          ...metadata,
          source: { ...metadata.source, kind: "gold_csv", is_demo: false },
        },
      }),
    ),
  );
  mount("/inspecoes?uc=UC-1004");

  await screen.findByRole("heading", { name: "O que motivou a investigação" });
  expect(collapsedSummaries()).toEqual([
    "Como a prioridade é calculada",
    "Cobertura do consumo no lote",
  ]);
  expect(
    screen.getByText("Regra provisória aguardando homologação."),
  ).toBeVisible();
  expect(
    screen.getByText(/A fila não informa uma janela temporal própria/),
  ).toBeVisible();
});
